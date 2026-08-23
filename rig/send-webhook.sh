#!/usr/bin/env bash
# =============================================================================
#  POST signed webhooks at the running rig and show what changed in MySQL.
#
#  Case 1  payment.authorized, VALID signature   -> row updated
#  Case 2  payment.authorized, VALID signature   -> row updated again (retry)
#  Case 3  payment.authorized, INVALID signature -> rejected, nothing changes
#
#  Case 3 is the one that proves the other two mean something: without a
#  negative control, "the row changed" is also consistent with the plugin not
#  checking signatures at all.
# =============================================================================
set -euo pipefail
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

cd "$(dirname "$0")"

SITE_URL="http://localhost:8080"
HOOK_URL="$SITE_URL/wp-admin/admin-post.php?action=rzp_wc_webhook"
RZP_WEBHOOK_SECRET="${RZP_WEBHOOK_SECRET:-rig-webhook-secret-synthetic}"
export RZP_WEBHOOK_SECRET

DC="docker compose"
PY="$(command -v python || command -v python3)"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()  { printf '    \033[32mOK\033[0m  %s\n' "$*"; }
die() { printf '\n\033[1;31mFAIL: %s\033[0m\n' "$*" >&2; exit 1; }

[ -f rig-state.sh ] || die "rig-state.sh missing. Run ./setup.sh first."
# shellcheck disable=SC1091
. ./rig-state.sh
[ -n "${ORDER_ID:-}" ] && [ -n "${RZP_ORDER_ID:-}" ] || die "rig-state.sh incomplete."

sql() { $DC exec -T db mariadb -uroot -proot --skip-ssl wordpress -e "$1"; }

show_row() {
  sql "SELECT id, order_id, rzp_order_id, rzp_webhook_notified_at AS notified_at,
              rzp_update_order_cron_status AS cron_status,
              CHAR_LENGTH(rzp_webhook_data) AS data_len, rzp_webhook_data
       FROM wp_rzp_webhook_requests
       WHERE order_id = $ORDER_ID\G"
}

mkdir -p out

post_case() {
  local label="$1" payment_id="$2" corrupt="$3"
  local body="out/${label}.json" sig http

  if [ "$corrupt" = "yes" ]; then
    sig="$("$PY" make-webhook.py --wc-order "$ORDER_ID" --rzp-order "$RZP_ORDER_ID" \
            --payment-id "$payment_id" --out "$body" --corrupt-signature)"
  else
    sig="$("$PY" make-webhook.py --wc-order "$ORDER_ID" --rzp-order "$RZP_ORDER_ID" \
            --payment-id "$payment_id" --out "$body")"
  fi

  # --data-binary @file sends the file bytes verbatim. Do NOT use --data here:
  # it strips newlines and would break the signature.
  http="$(curl -s -o "out/${label}.response" -w '%{http_code}' \
        -X POST "$HOOK_URL" \
        -H 'Content-Type: application/json' \
        -H "X-Razorpay-Signature: $sig" \
        --data-binary "@$body")"

  printf '    body      : %s (%s bytes)\n' "$body" "$(wc -c < "$body" | tr -d ' ')"
  printf '    signature : %s\n' "$sig"
  printf '    HTTP      : %s\n' "$http"
}

say "Target: $HOOK_URL"
printf '    WC order %s / Razorpay order %s\n' "$ORDER_ID" "$RZP_ORDER_ID"

say "BEFORE"
show_row

say "Case 1 - payment.authorized, VALID signature"
post_case "case1-valid" "pay_RIGSYNTH0000001" "no"
show_row

say "Case 2 - payment.authorized, VALID signature (redelivery, new payment id)"
post_case "case2-valid" "pay_RIGSYNTH0000002" "no"
show_row

say "Case 3 - payment.authorized, INVALID signature (negative control)"
post_case "case3-badsig" "pay_RIGSYNTH0000003" "yes"
show_row

cat <<'EOF'

  WHAT YOU SHOULD SEE
  -------------------
  Case 1  notified_at goes 0/NULL -> a unix timestamp; rzp_webhook_data
          becomes a 1-element JSON array holding pay_RIGSYNTH0000001.

  Case 2  notified_at advances; rzp_webhook_data is STILL a 1-element array,
          now holding pay_RIGSYNTH0000002.
          That is not a rig bug. saveWebhookEvent() at
          razorpay-webhook.php:208-212 does:
              $webhookEvents = $wpdb->get_results(...);            // list of rows
              $rzpWebhookData = (array) json_decode($webhookEvents['rzp_webhook_data']);
          get_results() returns a NUMERICALLY indexed array of row objects, so
          the string subscript is an undefined key -> null -> json_decode(null)
          -> null -> (array) null -> []. The prior events are discarded on
          every delivery. Redeliveries overwrite instead of accumulating.

  Case 3  NOTHING changes. The delivery is rejected at
          razorpay-webhook.php:131 (SignatureVerificationError) before any
          write. HTTP is still 200 - the plugin never signals rejection in the
          status code, it only writes a WooCommerce log line. That silence is
          exactly why the negative control is worth running.

  Next:  ./run-cron.sh     drain the deferred event through rzp_webhook_exec_cron
         ./read-order.sh   read the order row itself out of MySQL
EOF
