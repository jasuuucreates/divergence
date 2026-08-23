<?php
/* Run via: docker compose run --rm -T cli wp eval-file /rig/seed.php */
global $wpdb;

$product_id = (int) get_option('rig_product_id');
if (!$product_id || !wc_get_product($product_id)) {
    $p = new WC_Product_Simple();
    $p->set_name('Rig Test Product');
    $p->set_regular_price('499.00');
    $p->set_catalog_visibility('visible');
    $product_id = $p->save();
    update_option('rig_product_id', $product_id);
}

$order_id = (int) get_option('rig_order_id');
if (!$order_id || !wc_get_order($order_id)) {
    $o = wc_create_order();
    $o->add_product(wc_get_product($product_id), 1);
    $o->set_address(array(
        'first_name' => 'Test', 'last_name' => 'Buyer',
        'email' => 'buyer@rig.test', 'country' => 'IN',
    ), 'billing');
    $o->set_payment_method('razorpay');
    $o->calculate_totals();
    $o->set_status('pending');
    $order_id = $o->save();
    update_option('rig_order_id', $order_id);
}

$rzp_order_id = get_option('rig_rzp_order_id');
if (!$rzp_order_id) {
    // Shaped like a Razorpay order id but synthetic. Column is varchar(25).
    $rzp_order_id = 'order_RIG' . str_pad((string) $order_id, 11, '0', STR_PAD_LEFT);
    update_option('rig_rzp_order_id', $rzp_order_id);
}

$table  = $wpdb->prefix . 'rzp_webhook_requests';
$exists = $wpdb->get_var($wpdb->prepare(
    "SELECT id FROM $table WHERE integration=%s AND order_id=%d AND rzp_order_id=%s",
    'woocommerce', $order_id, $rzp_order_id
));
if (!$exists) {
    // Mirrors woo-razorpay.php:1484-1492 exactly.
    $wpdb->insert($table, array(
        'integration'                  => 'woocommerce',
        'order_id'                     => $order_id,
        'rzp_order_id'                 => $rzp_order_id,
        'rzp_webhook_data'             => '[]',
        'rzp_update_order_cron_status' => 0,
    ));
}

$o = wc_get_order($order_id);
echo "ORDER_ID="     . $order_id . "\n";
echo "RZP_ORDER_ID=" . $rzp_order_id . "\n";
echo "ORDER_TOTAL="  . $o->get_total() . "\n";
echo "ORDER_PAISE="  . ((int) round($o->get_total() * 100)) . "\n";
echo "HPOS="         . (get_option('woocommerce_custom_orders_table_enabled') === 'yes' ? 'yes' : 'no') . "\n";
