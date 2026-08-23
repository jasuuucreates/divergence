<?php
/* Run via: docker compose run --rm -T cli wp eval-file /rig/configure.php
   Writes ONLY to wp_options. The plugin directory is never touched.
   Note: we deliberately do NOT go through the WooCommerce settings-save
   action, because that would fire autoEnableWebhook() and attempt to
   register a webhook against the live Razorpay API. */
$settings = get_option('woocommerce_razorpay_settings');
if (!is_array($settings)) { $settings = array(); }

$settings['enabled']    = 'yes';
$settings['key_id']     = getenv('RZP_KEY_ID');
$settings['key_secret'] = getenv('RZP_KEY_SECRET');
// includes/razorpay-webhook.php:110 reads this first.
$settings['webhook_secret'] = getenv('RZP_WEBHOOK_SECRET');
$settings['payment_action']  = 'authorize';
// includes/utils.php:47-53 isDebugModeEnabled(). WITHOUT this the plugin
// logs absolutely nothing (includes/debug.php:19-25) and you debug blind.
$settings['enable_1cc_debug_mode'] = 'yes';
// Explicitly OFF: keeps the 1cc code paths (and their API calls) out of the way.
$settings['enable_1cc'] = 'no';

update_option('woocommerce_razorpay_settings', $settings);
// razorpay-webhook.php:110 falls back to this standalone option. Set both.
update_option('webhook_secret', getenv('RZP_WEBHOOK_SECRET'));

echo "settings_written\n";
