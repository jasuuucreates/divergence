#!/usr/bin/env bash
# Read the merchant-visible TERMINAL state of the order plus the deferred queue.
# This is the evidence. HTTP status is necessary but never sufficient.
set -eu
. "$(dirname "$0")/_docker.sh"   # portable docker discovery
Q(){ MSYS_NO_PATHCONV=1 docker compose exec -T db mariadb -uroot -proot --skip-ssl -N -B wordpress -e "$1" 2>/dev/null; }
echo "--- order (legacy posts) ---"
Q "SELECT ID, post_status FROM wp_posts WHERE post_type='shop_order';" | sed 's/^/  /'
echo "--- order meta of interest ---"
Q "SELECT meta_key, meta_value FROM wp_postmeta WHERE post_id=(SELECT MAX(ID) FROM wp_posts WHERE post_type='shop_order') AND meta_key IN ('_order_total','_payment_method','_transaction_id','_razorpay_order_id','rzp_payment_id','_paid_date','_date_paid');" | sed 's/^/  /'
echo "--- deferred webhook queue ---"
Q "SELECT id, rzp_webhook_notified_at, cron_status, LEFT(rzp_webhook_data,90) FROM wp_rzp_webhook_requests;" | sed 's/^/  /'
