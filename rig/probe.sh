#!/usr/bin/env bash
# =============================================================================
#  POST one signed webhook at the rig and print the HTTP status.
#
#    ./probe.sh                                   payment.authorized, valid sig
#    ./probe.sh --event refund.created            refund.created,     valid sig
#    ./probe.sh --bad-sig                         negative control
#    ./probe.sh --body out/mine.json              sign+send an existing file
#
#  READ THIS: the endpoint returns 200 for a FORGED signature too. process()
#  (includes/razorpay-webhook.php:80-141) just returns after logging. The HTTP
#  status is necessary evidence, never sufficient. Always pair it with the SQL
#  in RIG-RUNBOOK section 4.
# =============================================================================
set -euo pipefail
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'
cd "$(dirname "$0")"

EVENT="payment.authorized"; BAD_SIG="no"; BODY=""
PAYMENT_ID="pay_RIGSYNTH0000001"
while [ $# -gt 0 ]; do
  case "$1" in
    --event)      EVENT="$2"; shift 2 ;;
    --payment-id) PAYMENT_ID="$2"; shift 2 ;;
    --body)       BODY="$2"; shift 2 ;;
    --bad-sig)    BAD_SIG="yes"; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

SITE_URL="http://localhost:${HTTP_PORT:-8080}"
HOOK_URL="$SITE_URL/wp-admin/admin-post.php?action=rzp_wc_webhook"
RZP_WEBHOOK_SECRET="${RZP_WEBHOOK_SECRET:-rig-webhook-secret-synthetic}"
PY="$(command -v python || command -v python3)"

[ -f rig-state.sh ] || { echo "rig-state.sh missing. Run ./setup.sh first." >&2; exit 1; }
# shellcheck disable=SC1091
. ./rig-state.sh
mkdir -p out

if [ -z "$BODY" ]; then
  BODY="out/${EVENT}.json"
  "$PY" make-webhook.py --event "$EVENT" \
      --wc-order "$ORDER_ID" --rzp-order "$RZP_ORDER_ID" \
      --payment-id "$PAYMENT_ID" --amount "${ORDER_PAISE:-49900}" \
      --out "$BODY" >/dev/null
fi

# Sign the file bytes exactly as they sit on disk.
#   razorpay-sdk/src/Utility.php:53-55 -> hash_hmac('sha256', $payload, $secret)
#   $payload is php://input, read at razorpay-webhook.php:82.
# openssl equivalent, if you prefer:
#   openssl dgst -sha256 -hmac "$RZP_WEBHOOK_SECRET" -r "$BODY" | cut -d' ' -f1
SIG="$(RZP_WEBHOOK_SECRET="$RZP_WEBHOOK_SECRET" "$PY" - "$BODY" <<'PYSIGN'
import hashlib, hmac, os, sys
secret = os.environ["RZP_WEBHOOK_SECRET"].encode()
raw = open(sys.argv[1], "rb").read()
print(hmac.new(secret, raw, hashlib.sha256).hexdigest())
PYSIGN
)"

if [ "$BAD_SIG" = "yes" ]; then
  # Flip the last hex nibble: same length, same charset, wrong value.
  # Exercises hash_equals() (Utility.php:60), not a length check.
  LAST="${SIG: -1}"; [ "$LAST" = "0" ] && NEW="1" || NEW="0"
  SIG="${SIG%?}$NEW"
fi

# --data-binary sends the file verbatim. NEVER use --data here: it strips
# newlines and would change the bytes you just hashed.
HTTP="$(curl -sS -o "out/$(basename "$BODY").response" -w '%{http_code}' \
     -X POST "$HOOK_URL" \
     -H 'Content-Type: application/json' \
     -H "X-Razorpay-Signature: $SIG" \
     --data-binary "@$BODY")"

printf 'endpoint  : %s\n' "$HOOK_URL"
printf 'event     : %s\n' "$EVENT"
printf 'body      : %s (%s bytes)\n' "$BODY" "$(wc -c < "$BODY" | tr -d ' ')"
printf 'signature : %s%s\n' "$SIG" "$([ "$BAD_SIG" = yes ] && echo '   <-- DELIBERATELY WRONG')"
printf 'HTTP      : %s\n' "$HTTP"
exit 0
