#!/usr/bin/env bash
# =============================================================================
#  THE ORDERING EXPERIMENT
#
#  Same two events, same order, same signatures. Only the ARRIVAL ORDER differs.
#  Run A : payment.authorized  is drained first, then refund.created   (normal)
#  Run B : refund.created      arrives first, then payment.authorized  (inverted)
#
#  Razorpay's own docs state delivery order is not guaranteed. This plugin makes
#  the inversion the DEFAULT: payment.authorized is parked for >=300s for the
#  cron, while refund.created is handled synchronously on arrival.
#
#  We assert only on the CONVERGED TERMINAL state -- after the cron has run --
#  so "it is a transient our cron fixes" is not available as a rebuttal.
#
#  NOTE: runs in stub mode. api.razorpay.com is replaced by rig/stub/router.php,
#  so this tests the plugin's handling of a Razorpay-shaped response, not
#  Razorpay itself. Say so in any writeup.
# =============================================================================
# NOTE: deliberately NOT `set -e`. curl/docker emit harmless non-zero statuses
# mid-pipeline and an abort there would silently truncate the experiment.
set -uo pipefail
. "$(dirname "$0")/_docker.sh"   # portable docker discovery
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")"

SEC="rig-webhook-secret-synthetic"
URL="http://localhost:8080/wp-admin/admin-post.php?action=rzp_wc_webhook"
DC="docker compose"

q(){ $DC exec -T db mariadb -uroot -proot --skip-ssl -N -B wordpress -e "$1" 2>/dev/null; }
wpc(){ $DC run --rm -T cli wp "$@" 2>/dev/null | tr -d '\r'; }

new_order(){ wpc eval-file /rig/new_order.php | grep -E '^(ORDER_ID|RZP_ORDER_ID|PAISE)='; }

send(){ # $1 event  $2 wc_order  $3 rzp_order  $4 paise
  local f="out/x_$1_$2.json"
  python make-webhook.py --event "$1" --wc-order "$2" --rzp-order "$3" \
         --payment-id "pay_RIG$(printf '%011d' "$2")" --amount "$4" --out "$f" >/dev/null
  local sig; sig=$(python -c "
import hmac,hashlib,io
print(hmac.new(b'$SEC', io.open('$f','rb').read(), hashlib.sha256).hexdigest())")
  local code; code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$URL" \
      -H 'Content-Type: application/json' -H "X-Razorpay-Signature: $sig" --data-binary "@$f")
  printf '      -> %-20s HTTP %s\n' "$1" "$code"
}

drain(){ # make the parked row eligible, then run the cron
  q "UPDATE wp_rzp_webhook_requests SET rzp_webhook_notified_at=UNIX_TIMESTAMP()-600
     WHERE order_id=$1 AND rzp_update_order_cron_status=0;"
  wpc cron event run rzp_webhook_exec_cron >/dev/null 2>&1 || true
  printf '      -> cron drained\n'
}

final(){ q "SELECT post_status FROM wp_posts WHERE ID=$1;"; }

echo "============================================================================"
echo " ORDERING EXPERIMENT -- identical events, identical signatures, order differs"
echo "============================================================================"

# ---------------- RUN A : authorization settles first (the normal case) -------
eval "$(new_order)"; A=$ORDER_ID; AR=$RZP_ORDER_ID; AP=$PAISE
echo
echo "RUN A  order #$A  -- payment.authorized settles BEFORE the refund arrives"
send payment.authorized "$A" "$AR" "$AP"
drain "$A"
echo "      (order is now: $(final "$A"))"
send refund.created "$A" "$AR" "$AP"
drain "$A"
SA=$(final "$A")

# ---------------- RUN B : refund arrives first (the inverted case) ------------
eval "$(new_order)"; B=$ORDER_ID; BR=$RZP_ORDER_ID; BP=$PAISE
echo
echo "RUN B  order #$B  -- refund.created arrives BEFORE the authorization settles"
send refund.created "$B" "$BR" "$BP"
send payment.authorized "$B" "$BR" "$BP"
drain "$B"
SB=$(final "$B")

echo
echo "============================================================================"
printf ' RUN A  order #%-4s terminal state: %s\n' "$A" "$SA"
printf ' RUN B  order #%-4s terminal state: %s\n' "$B" "$SB"
echo "============================================================================"
if [ "$SA" != "$SB" ]; then
  echo " DIVERGENT. Same events, same signatures, only arrival order differs."
  echo " RUN B kept the customer's money AND will ship: the refund was dropped by"
  echo " refundedCreated()'s  if (\$order->needs_payment()) return;  guard, because"
  echo " the authorization had not settled yet."
else
  echo " CONVERGENT after the cron. The orderings agree -- this leg does not stand."
fi
