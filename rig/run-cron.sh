#!/usr/bin/env bash
# =============================================================================
#  Drain the deferred payment.authorized event on demand.
#
#  Why this script has to exist at all:
#  payment.authorized is NOT processed when it arrives. razorpay-webhook.php:153
#  parks it in wp_rzp_webhook_requests and returns. Razorpay's own docs say so
#  (.ai/context/WEBHOOK_FLOW.md: "Saved to table, NOT immediately processed").
#  It is drained later by the cron hook rzp_webhook_exec_cron, registered at
#  woo-razorpay.php:3354-3357 on a 5-minute schedule.
#
#  And the drain query (woo-razorpay.php:3393) only picks rows that are already
#  stale:
#      WHERE integration='woocommerce'
#        AND rzp_webhook_notified_at < <now - 300>
#        AND rzp_update_order_cron_status = 0
#
#  So a webhook you just sent is invisible to the cron for five minutes. Rather
#  than sit and wait, we move the row's clock backwards by 301 seconds. That is
#  a change to TEST DATA only - no plugin code is touched.
# =============================================================================
set -euo pipefail
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

cd "$(dirname "$0")"

DC="docker compose"
say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()  { printf '    \033[32mOK\033[0m  %s\n' "$*"; }
die() { printf '\n\033[1;31mFAIL: %s\033[0m\n' "$*" >&2; exit 1; }

[ -f rig-state.sh ] || die "rig-state.sh missing. Run ./setup.sh first."
# shellcheck disable=SC1091
. ./rig-state.sh

sql() { $DC exec -T db mariadb -uroot -proot --skip-ssl wordpress -e "$1"; }

say "1/4  Row before"
sql "SELECT id, order_id, rzp_webhook_notified_at AS notified_at,
            rzp_update_order_cron_status AS cron_status
     FROM wp_rzp_webhook_requests WHERE order_id = $ORDER_ID;"

say "2/4  Fast-forward past the 300s guard (test data only)"
sql "UPDATE wp_rzp_webhook_requests
     SET rzp_webhook_notified_at = rzp_webhook_notified_at - 301
     WHERE order_id = $ORDER_ID AND rzp_webhook_notified_at > 0;"
ok "notified_at backdated by 301s"

say "3/4  Run rzp_webhook_exec_cron"
# `wp cron event run` fires the hook directly, so it works even though
# DISABLE_WP_CRON is set in wp-config. If the event is not registered, fall
# back to calling the function the plugin hooks up at woo-razorpay.php:3447.
$DC run --rm -T cli wp cron event run rzp_webhook_exec_cron \
  || $DC run --rm -T cli wp eval 'execRzpWooWebhookEvents();'
ok "cron executed"

say "4/4  Row after + order status"
sql "SELECT id, order_id, rzp_webhook_notified_at AS notified_at,
            rzp_update_order_cron_status AS cron_status
     FROM wp_rzp_webhook_requests WHERE order_id = $ORDER_ID;"
$DC run --rm -T cli wp eval "\$o = wc_get_order($ORDER_ID); echo 'order_status=' . \$o->get_status() . \"\n\";"

cat <<'EOF'

  WHAT YOU SHOULD SEE, AND THE HONEST LIMIT
  -----------------------------------------
  cron_status flips 0 -> 2. That is the cron confirming it consumed the row
  (woo-razorpay.php:3411-3420).

  The ORDER ITSELF STAYS "pending", and that is correct behaviour, not a
  failure of the rig. paymentAuthorized() at razorpay-webhook.php:343 calls
  getPaymentEntity(), which does a live
      GET https://api.razorpay.com/v1/payments/<id>
  Our credentials are synthetic, so that call 401s, getPaymentEntity() returns
  false (razorpay-webhook.php, catch block -> `return false`), and
  paymentAuthorized() returns before it can mark the order paid.

  Note the ordering bug this exposes: the cron sets cron_status = 2 AFTER
  paymentAuthorized() returns, and it does not check whether the work actually
  succeeded. A row whose payment fetch failed is still marked processed and
  will never be retried.

  To drive the order all the way to "processing" you need ONE of:
    a) real Razorpay TEST-mode key_id/key_secret plus a real test payment id
       that those keys can fetch, or
    b) a local stub for api.razorpay.com. The vendored SDK exposes
       Api::setBaseUrl() (razorpay-sdk/src/Api.php:54-57), so an mu-plugin can
       repoint it without editing plugin files.
  Both are out of scope here: (a) needs live-ish credentials, (b) means the
  thing under test is no longer talking to the real client code path.
EOF
