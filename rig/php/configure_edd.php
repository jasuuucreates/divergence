<?php
// Configure razorpay-edd exactly as a merchant would through the settings screen, but via
// update_option so autoEnableWebhook() (which would call the live API) never fires.
$s = get_option('edd_settings', array());
$s['gateways']        = array('razorpay' => 1);
$s['default_gateway'] = 'razorpay';
$s['razorpay_key_id']     = 'rzp_test_RIGSYNTHETIC';
$s['razorpay_key_secret'] = 'rig_synthetic_secret_not_a_credential';
$s['enable_webhook']  = '1';
$s['webhook_secret']  = 'rig-webhook-secret-synthetic';
$s['currency']        = 'INR';
$s['test_mode']       = '1';
update_option('edd_settings', $s);
echo "EDD_GATEWAY=razorpay\n";
echo "EDD_WEBHOOK_SECRET=" . $s['webhook_secret'] . "\n";
