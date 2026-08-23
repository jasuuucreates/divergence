<?php
/*
 * Plugin Name: RIG - repoint Razorpay SDK base URL
 * Description: TEST RIG ONLY. Points razorpay-sdk at a local stub so the
 *              webhook cron can complete offline. Installed only when
 *              RIG_STUB=1. Does not modify razorpay-woocommerce.
 */
add_action('plugins_loaded', function () {
    if (!class_exists('\Razorpay\Api\Api')) { return; }
    // Preserve whatever key/secret are currently set: the SDK keeps them in
    // protected statics and the constructor overwrites them.
    $api = new \Razorpay\Api\Api(
        \Razorpay\Api\Api::getKey(),
        \Razorpay\Api\Api::getSecret()
    );
    $api->setBaseUrl('http://rzpstub:8000');
}, 5);

// Keep the rig hermetic: swallow the telemetry POST to
// https://lumberjack.razorpay.com/v1/track (includes/plugin-instrumentation.php:242,
// timeout 45s) instead of shipping synthetic payloads off-box.
add_filter('pre_http_request', function ($pre, $args, $url) {
    if (strpos($url, 'lumberjack.razorpay.com') !== false) {
        return array(
            'headers'  => array(),
            'body'     => '{"rig":"telemetry suppressed"}',
            'response' => array('code' => 200, 'message' => 'OK'),
            'cookies'  => array(),
            'filename' => null,
        );
    }
    return $pre;
}, 10, 3);
