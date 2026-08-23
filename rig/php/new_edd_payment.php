<?php
/*
 * Seed ONE fresh EDD payment for a harness trial.
 *
 * EDD 3.x moved orders out of wp_posts into its own tables, and creates them lazily, so the
 * install routine has to be forced before the first payment. EDD_Payment survives in 3.x as a
 * back-compat shim over the new store, which is what razorpay-edd itself uses -- so seeding
 * through it exercises the same path the plugin does.
 */
if (function_exists('edd_install')) { edd_install(); }
if (class_exists('EDD\Database\Tables\Orders')) {
    $t = new EDD\Database\Tables\Orders();
    if (!$t->exists()) { $t->install(); }
}

$download_id = (int) get_option('rig_edd_download_id');
if (!$download_id) {
    $download_id = wp_insert_post(array(
        'post_title'  => 'Rig Download',
        'post_type'   => 'download',
        'post_status' => 'publish',
    ));
    update_post_meta($download_id, 'edd_price', '499.00');
    update_option('rig_edd_download_id', $download_id);
}

$p = new EDD_Payment();
$p->add_download($download_id, array('item_price' => 499.00));
$p->total     = 499.00;
$p->currency  = 'INR';
$p->gateway   = 'razorpay';
$p->email     = 'rig@example.invalid';
$p->first_name = 'Rig';
$p->last_name  = 'Tester';
$p->status    = 'pending';
$p->save();

echo "ORDER_ID="   . $p->ID . "\n";
echo "PAISE="      . (int) round($p->total * 100) . "\n";
echo "STATUS="     . $p->status . "\n";
