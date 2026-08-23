#!/usr/bin/env bash
# =============================================================================
#  Razorpay-WooCommerce webhook rig -- one-shot setup.  Idempotent.
#  Windows 11 + Docker Desktop (WSL2) + Git Bash.
#
#  Result: WordPress 6.9.4 + WooCommerce 10.6.2 + MariaDB 10.11 +
#  the UNMODIFIED razorpay-woocommerce plugin at v4.8.7, webhook secret set,
#  one test order created, order id printed.
#
#  Optional:  RIG_STUB=1 ./setup.sh   also stands up the fake API (section 8).
# =============================================================================
set -euo pipefail

# --- Git Bash / MSYS path-mangling trap --------------------------------------
# MSYS rewrites anything shaped like a Unix path before handing it to a
# non-MSYS binary (docker.exe). Without these, /var/www/html becomes
# C:/Program Files/Git/var/www/html and every wp-cli call fails obscurely.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

cd "$(dirname "$0")"
RIG_DIR="$(pwd)"

SITE_URL="http://localhost:${HTTP_PORT:-8080}"
ADMIN_USER="admin"; ADMIN_PASS="admin-rig-pw"; ADMIN_EMAIL="admin@rig.test"

PLUGIN_REPO="https://github.com/razorpay/razorpay-woocommerce.git"
PLUGIN_TAG="v4.8.7"
# v4.8.7^{} verified 2026-08-23 == master HEAD.
PLUGIN_SHA="4af03b1cddec1c73e18a72011556ead745f1e9f6"
WC_VERSION="10.6.2"          # woo-razorpay.php:9  "WC tested up to: 10.6.2"

# Deliberately NOT credential-shaped. Nothing here authenticates anywhere.
RZP_KEY_ID="${RZP_KEY_ID:-SYNTHETIC-KEY-ID-NOT-A-REAL-KEY}"
RZP_KEY_SECRET="${RZP_KEY_SECRET:-SYNTHETIC-KEY-SECRET-NOT-REAL}"
RZP_WEBHOOK_SECRET="${RZP_WEBHOOK_SECRET:-rig-webhook-secret-synthetic}"
RIG_STUB="${RIG_STUB:-0}"

DC="docker compose"
say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok(){  printf '    \033[32mOK\033[0m  %s\n' "$*"; }
die(){ printf '\n\033[1;31mFAIL: %s\033[0m\n' "$*" >&2; exit 1; }
wpc(){ $DC run --rm -T cli wp "$@"; }
sql(){ $DC exec -T db mariadb -uroot -proot --skip-ssl wordpress -e "$1"; }

# --- 0/9 preflight -----------------------------------------------------------
say "0/9  Preflight"
command -v docker >/dev/null || die "docker not on PATH. Start Docker Desktop, reopen Git Bash."
docker info >/dev/null 2>&1  || die "Docker daemon unreachable. Is Docker Desktop running?"
command -v git  >/dev/null || die "git not on PATH."
command -v curl >/dev/null || die "curl not on PATH."
PY="$(command -v python || command -v python3)" || die "python not on PATH."
mkdir -p out php stub
ok "docker / git / curl / python present"

# --- 1/9 fetch the REAL plugin ----------------------------------------------
say "1/9  Fetch the REAL plugin, pinned at ${PLUGIN_TAG}"
mkdir -p plugin
if [ ! -d plugin/razorpay-woocommerce/.git ]; then
  # -c core.autocrlf=false is load-bearing: Git for Windows defaults to
  # autocrlf=true, which would rewrite every .php file's line endings on
  # checkout. `git status` would still say "clean", but the bytes on disk
  # would NOT match upstream -- and we are claiming "unmodified".
  git -c core.autocrlf=false -c core.eol=lf clone --quiet --depth 1 \
      --branch "$PLUGIN_TAG" "$PLUGIN_REPO" plugin/razorpay-woocommerce
fi
ACTUAL_SHA="$(git -C plugin/razorpay-woocommerce rev-parse HEAD)"
[ "$ACTUAL_SHA" = "$PLUGIN_SHA" ] || die "plugin HEAD is $ACTUAL_SHA, expected $PLUGIN_SHA"
[ -z "$(git -C plugin/razorpay-woocommerce status --porcelain)" ] \
  || die "plugin working tree is MODIFIED. The rig must run stock code."
ok "razorpay-woocommerce @ $PLUGIN_SHA -- clean, unmodified"

# --- 2/9 bring up containers -------------------------------------------------
say "2/9  Start MariaDB + WordPress"
if [ "$RIG_STUB" = "1" ]; then
  $DC up -d db wordpress rzpstub
  printf '    \033[1;33mSTUB MODE: api.razorpay.com is faked. See RIG-RUNBOOK section 8.\033[0m\n'
else
  $DC up -d db wordpress
fi
ok "containers up"

# --- 3/9 wait for HTTP -------------------------------------------------------
say "3/9  Wait for WordPress over HTTP"
CODE=""
for i in $(seq 1 90); do
  CODE="$(curl -s -o /dev/null -w '%{http_code}' "$SITE_URL/wp-admin/install.php" || true)"
  case "$CODE" in 200|30[0-9]) break ;; esac
  [ "$i" = 90 ] && die "WordPress never answered (last HTTP $CODE). Try: $DC logs wordpress"
  sleep 2
done
ok "WordPress answering on $SITE_URL (HTTP $CODE)"

# --- 4/9 install core --------------------------------------------------------
say "4/9  Install WordPress core"
if wpc core is-installed 2>/dev/null; then ok "already installed"; else
  wpc core install --url="$SITE_URL" --title="Razorpay Webhook Rig" \
    --admin_user="$ADMIN_USER" --admin_password="$ADMIN_PASS" \
    --admin_email="$ADMIN_EMAIL" --skip-email
  ok "core installed"
fi

# --- 5/9 WooCommerce ---------------------------------------------------------
say "5/9  Install + activate WooCommerce ${WC_VERSION}"
if wpc plugin is-active woocommerce 2>/dev/null; then ok "already active"; else
  wpc plugin install woocommerce --version="$WC_VERSION" --activate
  ok "woocommerce $WC_VERSION active"
fi
wpc option update woocommerce_currency INR            >/dev/null
wpc option update woocommerce_default_country "IN:KA" >/dev/null

# --- 6/9 activate the plugin under test --------------------------------------
say "6/9  Activate razorpay-woocommerce"
if wpc plugin is-active razorpay-woocommerce 2>/dev/null; then ok "already active"; else
  wpc plugin activate razorpay-woocommerce
  ok "razorpay-woocommerce active"
fi
# The webhook table is created by top-level code inside woocommerce_razorpay_init
# (woo-razorpay.php:3449-3477), guarded by option 'rzp_webhook_setup'. Any full
# WP bootstrap triggers it; the wp-cli call above already did.

# --- 6b/9 optional stub wiring ----------------------------------------------
if [ "$RIG_STUB" = "1" ]; then
  say "6b/9  Install mu-plugin that repoints the SDK base URL at the stub"
  wpc eval 'if (!is_dir(WP_CONTENT_DIR."/mu-plugins")) { mkdir(WP_CONTENT_DIR."/mu-plugins", 0775, true); } echo "ok\n";' >/dev/null
  $DC run --rm -T cli sh -c 'cp /rig/mu-rig-api-base.php /var/www/html/wp-content/mu-plugins/mu-rig-api-base.php'
  ok "mu-plugin installed (plugin files still untouched)"
fi

# --- 7/9 gateway settings ----------------------------------------------------
say "7/9  Configure gateway settings + webhook secret"
$DC run --rm -T \
  -e RZP_KEY_ID="$RZP_KEY_ID" \
  -e RZP_KEY_SECRET="$RZP_KEY_SECRET" \
  -e RZP_WEBHOOK_SECRET="$RZP_WEBHOOK_SECRET" \
  cli wp eval-file /rig/configure.php >/dev/null
ok "webhook_secret configured (synthetic)"

TABLE="$(sql "SHOW TABLES LIKE 'wp_rzp_webhook_requests';" | tail -n +2 | tr -d '\r')"
[ -n "$TABLE" ] || die "wp_rzp_webhook_requests missing. Check: $DC logs wordpress"
ok "table wp_rzp_webhook_requests exists"

# --- 8/9 test order + the checkout row --------------------------------------
say "8/9  Create one test order + seed the checkout row"
# THE UPDATE TRAP:
# saveWebhookEvent() (includes/razorpay-webhook.php:213-225) issues an UPDATE
# keyed on (integration, order_id, rzp_order_id). It is NOT an insert. That row
# is normally created during checkout at woo-razorpay.php:1484-1492, right after
# the plugin creates a Razorpay order over the API. We cannot create a real
# Razorpay order, so we seed the identical row. Without it a perfectly-signed
# webhook updates ZERO rows and the rig looks broken with no error anywhere.
SEED_OUT="$($DC run --rm -T cli wp eval-file /rig/seed.php | tr -d '\r')"
echo "$SEED_OUT" | sed 's/^/    /'
printf '%s\n' "$SEED_OUT" > "$RIG_DIR/rig-state.sh"
ok "test order created + checkout row seeded"

# --- 9/9 summary -------------------------------------------------------------
say "9/9  Summary"
# shellcheck disable=SC1090
. "$RIG_DIR/rig-state.sh"
cat <<EOF

  Site            : $SITE_URL   (admin / $ADMIN_PASS)
  Webhook URL     : $SITE_URL/wp-admin/admin-post.php?action=rzp_wc_webhook
  Webhook secret  : $RZP_WEBHOOK_SECRET
  WC ORDER ID     : $ORDER_ID        <-- this is the order id
  Order total     : $ORDER_TOTAL
  Razorpay order  : $RZP_ORDER_ID
  HPOS enabled    : $HPOS
  Stub mode       : $RIG_STUB

  Next:
    ./probe.sh --event payment.authorized
    ./probe.sh --event payment.authorized --bad-sig     # negative control
    (then section 5 of RIG-RUNBOOK to drain the cron, section 4 to read SQL)

EOF
ok "rig ready"
