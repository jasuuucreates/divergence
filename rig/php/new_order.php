<?php
/*
 * Create ONE fresh WooCommerce order plus its rzp_webhook_requests row.
 * Each experiment run needs a virgin order: saveWebhookEvent() does an UPDATE,
 * not an INSERT, so the queue row must already exist (same as seed.php).
 * Prints ORDER_ID / RZP_ORDER_ID / PAISE for the caller to consume.
 */
global $wpdb;

$product_id = (int) get_option('rig_product_id');
if (!$product_id) {
    $p = new WC_Product_Simple();
    $p->set_name('Rig Widget');
    $p->set_regular_price('499.00');
    $product_id = $p->save();
    update_option('rig_product_id', $product_id);
}

$o = wc_create_order();
$o->add_product(wc_get_product($product_id), 1);
$o->set_payment_method('razorpay');
$o->calculate_totals();
$o->save();
$order_id = $o->get_id();

$rzp_order_id = 'order_RIG' . str_pad((string) $order_id, 11, '0', STR_PAD_LEFT);
$paise = (int) round(((float) $o->get_total()) * 100);

$table = $wpdb->prefix . 'rzp_webhook_requests';
$wpdb->insert($table, array(
    'integration'                   => 'woocommerce',
    'order_id'                      => $order_id,
    'rzp_order_id'                  => $rzp_order_id,
    'rzp_webhook_data'              => '',
    'rzp_webhook_notified_at'       => time(),
    'rzp_update_order_cron_status'  => 0,
));

echo "ORDER_ID=$order_id\n";
echo "RZP_ORDER_ID=$rzp_order_id\n";
echo "PAISE=$paise\n";
echo "STATUS=" . $o->get_status() . "\n";
