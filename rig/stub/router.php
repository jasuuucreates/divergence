<?php
/*
 * Fake api.razorpay.com for the rig. Started only with the `stub` profile.
 * Run as: php -S 0.0.0.0:8000 /stub/router.php
 *
 * The SDK builds URLs as  {base}/v1/{relative}  (razorpay-sdk/src/Api.php:85-88)
 * and Entity::fetch() (razorpay-sdk/src/Entity.php:23-31) hits  payments/{id}.
 * Request::checkErrors() (razorpay-sdk/src/Request.php:93-112) only throws on a
 * non-2xx, so any 200 + JSON is accepted.
 */
header('Content-Type: application/json');
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);

// FAULT INJECTION. A payment id beginning pay_FAULT makes this stub answer 500, which is
// what api.razorpay.com does on a transient failure (timeout, 5xx, rate limit). The plugin's
// getPaymentEntity() then returns false and paymentAuthorized() returns silently -- while the
// cron still marks the row processed. Without this, property P4 can never fail, and a property
// that cannot fail is not evidence. The trigger is encoded in the payment id ON PURPOSE so it
// is visible in the request transcript rather than hidden in server config.
if (preg_match('#^/v1/payments/(pay_FAULT[A-Za-z0-9_]*)$#', $path, $fm)) {
    http_response_code(500);
    echo json_encode(array('error' => array(
        'code' => 'SERVER_ERROR',
        'description' => 'rig: induced transient failure',
    )));
    exit;
}

if (preg_match('#^/v1/payments/([A-Za-z0-9_]+)$#', $path, $m)) {
    // Derive the WooCommerce order id from the payment id so every order under
    // test gets its OWN answer. The rig mints ids as pay_RIG<zero-padded id>.
    // Without this the stub returned one hardcoded order id for every payment,
    // which silently sent refunds to the wrong order and produced a FALSE
    // NEGATIVE in exp_ordering.sh. Instrument bugs look exactly like real
    // results, so this derivation is deliberate and load-bearing.
    // P5 AMOUNT INTEGRITY: pay_UNDER... answers with a DELIBERATELY MISMATCHED amount, so the
    // harness can observe whether the integration defends the invariant "amount paid == amount
    // ordered". Like the fault trigger, this lives in the payment id so it is visible in the
    // request transcript rather than hidden in configuration.
    $underpay = (strpos($m[1], 'pay_UNDER') === 0);

    $wcOrder = getenv('RIG_WC_ORDER_ID') ?: '1';
    if (preg_match('#^pay_(?:RIG|UNDER|FAULT|SECOND)0*([0-9]+)$#', $m[1], $om)) {
        $wcOrder = $om[1];
    }
    $rzpOrder = 'order_RIG' . str_pad($wcOrder, 11, '0', STR_PAD_LEFT);
    // 'captured' makes paymentAuthorized() (razorpay-webhook.php:344) set
    // $success = true without attempting a capture call.
    echo json_encode(array(
        'id'       => $m[1],
        'entity'   => 'payment',      // required: Entity::request() checks this
        'amount'   => $underpay ? 100 : (int) (getenv('RIG_AMOUNT_PAISE') ?: 49900),
        'currency' => 'INR',
        'status'   => 'captured',
        'captured' => true,
        'order_id' => $rzpOrder,
        'invoice_id' => null,
        // Fields below were ADDED after harness/stubcheck.py found them: each is in Razorpay's
        // documented Payments Entity AND is read by at least one integration under test, but the
        // stub was omitting them -- so the plugin received null where production sends a value.
        // A stub that silently omits a field the code under test reads can change a verdict
        // without anyone noticing, which makes it the most dangerous component in the harness.
        // Values are obviously synthetic on purpose. The contact is a 10-digit form rather than a
        // 12-digit one so it cannot be mistaken for a government identifier.
        'method'   => 'upi',
        'email'    => 'rig@example.invalid',
        'contact'  => '9000000000',
        'description' => 'rig synthetic payment',
        'international' => false,
        'amount_refunded' => 0,
        'refund_status' => null,
        'fee'      => null,
        'tax'      => null,
        'error_code' => null,
        'error_description' => null,
        'error_source' => null,
        'error_step' => null,
        'error_reason' => null,
        'notes'    => array('woocommerce_order_id' => (string) $wcOrder),
        'created_at' => time(),
    ));
    exit;
}

// Everything else: a harmless 200 so the SDK never throws.
http_response_code(200);
echo json_encode(array('rig' => 'stub', 'path' => $path));
