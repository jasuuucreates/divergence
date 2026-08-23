#!/usr/bin/env bash
# =============================================================================
#  Read the order row straight out of MySQL - no WordPress, no PHP in the way.
#
#  WooCommerce stores orders in one of two places and you must know which:
#
#    HPOS on  (High-Performance Order Storage, the default for fresh installs
#             since WooCommerce 8.2)  ->  wp_wc_orders + wp_wc_orders_meta
#    HPOS off (legacy)                ->  wp_posts (post_type='shop_order')
#                                         + wp_postmeta
#
#  Guessing wrong gives you an empty result set and looks like "the order was
#  never created". This script checks the option and picks the right query.
# =============================================================================
set -euo pipefail
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

cd "$(dirname "$0")"

DC="docker compose"
say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mFAIL: %s\033[0m\n' "$*" >&2; exit 1; }

[ -f rig-state.sh ] || die "rig-state.sh missing. Run ./setup.sh first."
# shellcheck disable=SC1091
. ./rig-state.sh

sql() { $DC exec -T db mariadb -uroot -proot --skip-ssl wordpress -e "$1"; }

HPOS_OPT="$(sql "SELECT option_value FROM wp_options
                 WHERE option_name='woocommerce_custom_orders_table_enabled';" \
            | tail -n +2 | tr -d '\r' | head -1)"
[ -n "$HPOS_OPT" ] || HPOS_OPT="no"

say "Storage mode"
printf '    woocommerce_custom_orders_table_enabled = %s  ->  %s\n' \
  "$HPOS_OPT" \
  "$( [ "$HPOS_OPT" = "yes" ] && echo 'HPOS (wp_wc_orders)' || echo 'legacy (wp_posts)' )"

if [ "$HPOS_OPT" = "yes" ]; then
  say "Order row  (HPOS: wp_wc_orders)"
  sql "SELECT id, status, currency, total_amount, payment_method,
              payment_method_title, date_created_gmt
       FROM wp_wc_orders WHERE id = $ORDER_ID\G"

  say "Order meta  (wp_wc_orders_meta)"
  sql "SELECT meta_key, LEFT(meta_value, 120) AS meta_value
       FROM wp_wc_orders_meta WHERE order_id = $ORDER_ID ORDER BY meta_key;"
else
  say "Order row  (legacy: wp_posts)"
  sql "SELECT ID, post_status, post_type, post_date_gmt
       FROM wp_posts WHERE ID = $ORDER_ID\G"

  say "Order meta  (wp_postmeta)"
  sql "SELECT meta_key, LEFT(meta_value, 120) AS meta_value
       FROM wp_postmeta WHERE post_id = $ORDER_ID ORDER BY meta_key;"
fi

say "Razorpay webhook queue  (wp_rzp_webhook_requests)"
# Schema is created by the plugin at woo-razorpay.php:3459-3467.
sql "SELECT id, integration, order_id, rzp_order_id,
            rzp_webhook_notified_at AS notified_at,
            rzp_update_order_cron_status AS cron_status,
            rzp_webhook_data
     FROM wp_rzp_webhook_requests WHERE order_id = $ORDER_ID\G"

say "Order status via WooCommerce itself (cross-check)"
$DC run --rm -T cli wp eval "\$o = wc_get_order($ORDER_ID);
  echo 'id=' . \$o->get_id() . \"\n\";
  echo 'status=' . \$o->get_status() . \"\n\";
  echo 'total=' . \$o->get_total() . ' ' . \$o->get_currency() . \"\n\";
  echo 'payment_method=' . \$o->get_payment_method() . \"\n\";"

say "Plugin log file (WooCommerce logger, source 'razorpay-logs')"
# includes/debug.php:17-25 logs through wc_get_logger() with that source, but
# ONLY when woocommerce_razorpay_settings['enable_1cc_debug_mode'] === 'yes'
# (includes/utils.php:47-53). setup.sh sets that flag for you.
$DC exec -T wordpress sh -c 'ls -1 /var/www/html/wp-content/uploads/wc-logs/ 2>/dev/null | grep -i razorpay || echo "    (no razorpay log file yet)"'

cat <<'EOF'

  RAW SQL, if you would rather run it yourself
  --------------------------------------------
  Open a shell on the database:

      docker compose exec db mariadb -uroot -proot --skip-ssl wordpress

  Then:

      -- the order (HPOS)
      SELECT id, status, total_amount, payment_method FROM wp_wc_orders;

      -- the order (legacy)
      SELECT ID, post_status FROM wp_posts WHERE post_type='shop_order';

      -- the deferred webhook queue
      SELECT * FROM wp_rzp_webhook_requests\G

      -- the configured gateway settings (serialized PHP array)
      SELECT option_value FROM wp_options
       WHERE option_name='woocommerce_razorpay_settings'\G

  The db port is also published on 127.0.0.1:3307 if you want a GUI client.
EOF
