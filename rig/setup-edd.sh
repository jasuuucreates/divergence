#!/usr/bin/env bash
# =============================================================================
#  Second target: razorpay-edd.
#
#  Run AFTER ./setup.sh. Adds Easy Digital Downloads and razorpay-edd to the same
#  rig, so `python harness/matrix.py` can compare both plugins in one command.
#
#  Why a separate script rather than part of setup.sh: only ONE gateway plugin can
#  be active at a time (both define RAZORPAY_SIGNATURE, RAZORPAY_PAYMENT_ID and
#  RAZORPAY_ORDER_ID, and PHP warns when the second one loads). The harness switches
#  between them per measurement; setup just has to make both available.
#
#  A note on a bug this script exists because of: Docker CREATES an empty directory
#  on the host for any bind mount whose source does not exist. So `[ -d plugin/x ]`
#  is true even when nothing was ever cloned there, and a `git clone` guarded that
#  way is silently skipped. The activation then fails with "No plugins activated",
#  which reads like a WordPress problem rather than a missing checkout. We test for
#  a FILE we know the repo contains.
# =============================================================================
set -uo pipefail
. "$(dirname "$0")/_docker.sh"
cd "$(dirname "$0")"

DC="docker compose"
say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()  { printf '    \033[32mOK\033[0m  %s\n' "$*"; }
die() { printf '\n\033[1;31mFAIL: %s\033[0m\n' "$*" >&2; exit 1; }
wpc() { $DC run --rm -T cli wp "$@" 2>&1 | grep -viE '^Warning:|^\[[0-9]{2}-[A-Za-z]{3}-'; }

EDD_REF="master"

say "1/5  Fetch razorpay-edd (unmodified)"
# Test for a known FILE, not the directory -- see the header note about bind mounts.
if [ ! -f plugin/razorpay-edd/razorpay-edd.php ]; then
  rm -rf plugin/razorpay-edd
  git clone -q --depth 1 --branch "$EDD_REF" \
    https://github.com/razorpay/razorpay-edd.git plugin/razorpay-edd \
    || die "clone failed"
fi
[ -f plugin/razorpay-edd/razorpay-edd.php ] || die "clone produced no razorpay-edd.php"
EDD_SHA="$(cd plugin/razorpay-edd && git rev-parse --short HEAD)"
[ -z "$(cd plugin/razorpay-edd && git status --porcelain)" ] \
  || die "razorpay-edd working tree is MODIFIED. The rig must run stock code."
ok "razorpay-edd @ $EDD_SHA -- clean, unmodified"

say "2/5  Ensure the mount is live"
$DC up -d db wordpress >/dev/null 2>&1
for i in $(seq 1 30); do
  $DC exec -T wordpress test -f /var/www/html/wp-content/plugins/razorpay-edd/razorpay-edd.php \
    >/dev/null 2>&1 && break
  [ "$i" = 30 ] && die "the container cannot see razorpay-edd. Is the ./plugin/razorpay-edd mount in docker-compose.yml?"
  sleep 1
done
ok "container can see the plugin"

say "3/5  Install Easy Digital Downloads"
wpc plugin is-installed easy-digital-downloads >/dev/null 2>&1 \
  || wpc plugin install easy-digital-downloads >/dev/null
wpc plugin activate easy-digital-downloads >/dev/null
ok "easy-digital-downloads active"

say "4/5  Activate razorpay-edd"
# Deactivate the WooCommerce pair first: two gateway plugins defining the same
# constants cannot be co-active cleanly.
wpc plugin deactivate razorpay-woocommerce woocommerce >/dev/null 2>&1
wpc plugin activate razorpay-edd >/dev/null
wpc plugin list --status=active --field=name | grep -qx razorpay-edd \
  || die "razorpay-edd did not activate. Check: $DC run --rm cli wp plugin list"
ok "razorpay-edd active"

say "5/5  Configure the gateway"
wpc eval-file /rig/configure_edd.php | sed 's/^/    /'
ok "gateway configured (synthetic values only)"

cat <<EOF

  Both targets are now installed. Only one is active at a time; the harness
  switches between them and verifies the switch took effect.

  Next:
    python harness/matrix.py     # both targets, one command

EOF
