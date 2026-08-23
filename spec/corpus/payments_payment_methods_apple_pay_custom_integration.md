---
title: Integration Steps
description: Accept Apple Pay payments from international customers on your own checkout UI using the Razorpay Custom Checkout SDK.
---

# Integration Steps

Apple Pay is a secure, contactless payment method that lets customers pay using their Apple devices with Face ID/Touch ID authentication. With the Custom Checkout headless SDK, you check Apple Pay eligibility and either let Razorpay render the Apple Pay button or render your own — all on your existing Custom Checkout integration, with no redirect. Know more about [Apple Pay](https://www.apple.com/apple-pay/).

This integration works with your existing card payment flow: check eligibility, render a button and initiate the payment with one additional `app` parameter.

  
### Advantages

     - Accept payments in over 120 currencies from international customers.
     - Reduce checkout time with one-touch biometric payments (Face ID/Touch ID).
     - Full control of where and how the Apple Pay button appears on your page.
     - Razorpay encapsulates device eligibility — no need to integrate the Apple Pay JS API or write capability-detection logic yourself.
     - No need to handle Apple certificates or domain verification beyond hosting one file — Razorpay manages the rest.
    

## Prerequisites

Before you begin, ensure you have:

- An existing Razorpay Custom Checkout integration.
- Apple Pay enabled and International Payments enabled on your Razorpay account.
- HTTPS on your website — Apple Pay requires a secure context.
- Your API Key Id. Generate [API Keys](https://razorpay.com/docs/build/llm-docs/api/authentication.md#generate-api-keys) from the Dashboard. Use Live Mode keys to accept real payments.
- Apple Pay domain verification completed for your domain (host the domain association file; Razorpay registers it with Apple).

## Integration Steps

Follow the steps given below.

### 1.1 Create an Order on Your Server

An order should be created for every payment.

- Create an order using the [Orders API](https://razorpay.com/docs/build/llm-docs/api/orders/create.md). This is a server-side call.
- Pass the returned `order_id` to your frontend. This ties the order to the payment and secures the request from tampering.

**WARN**

**Watch Out!**

Payments made without an `order_id` cannot be captured and will be automatically refunded. Create an order before initiating payment.

```curl: Request
curl -X POST https://api.razorpay.com/v1/orders \
 -u [YOUR_KEY_ID]:[YOUR_KEY_SECRET] \
 -H 'content-type:application/json' \
 -d '{
     "amount": 50000,
     "currency": "USD",
     "receipt": "receipt_1"
 }'
```

The response includes an `id` (for example, `order_XXXXXXXXXX`). Pass this to your frontend for SDK initialisation. For the full list of order request and response parameters, see the [Create an Order API](https://razorpay.com/docs/build/llm-docs/api/orders/create.md).

### 1.2 Load the Custom Checkout Script

Include the Custom Checkout script, preferably in the `` of your page:

```html: HTML

```

**INFO**

**Handy Tips**

Load the script from `https://checkout.razorpay.com/v1/razorpay.js` rather than serving a copy. This keeps updates and fixes automatic. Existing Custom Checkout merchants already load this script.

### 1.3 Initialise the SDK

Initialise Razorpay with your key and the `order_id` created in step 1.1. Provide a handler to receive the successful payment response (you can also use event listeners — see step 1.6).

```js: JavaScript
var razorpay = new Razorpay({
  key: 'rzp_live_xxx',
  order_id: 'order_XXXXXXXXXX',   // created server-side at page load
  contact: '9123456789',
  email: 'gaurav.kumar@example.com',
  handler: function (response) {
    // response.razorpay_payment_id
    // response.razorpay_order_id
    // response.razorpay_signature   // verify on your server
  }
});
```

  
### Initialisation Parameters

Parameter | Type | Required | Description
---
`key` | string | Yes | API Key ID (`rzp_test_*` or `rzp_live_*`).
---
`order_id` | string | Yes | Order ID generated via the Orders API.
---
`contact` | string | Optional | Customer's phone number, used to prefill the contact field.
---
`email` | string | Optional | Customer's email address, used to prefill the email field.
---
`handler` | function | Optional | Called with the success response (`razorpay_payment_id`, `razorpay_order_id`, `razorpay_signature`). Alternatively, use event listeners (step 1.6).

    

### 1.4 Check Apple Pay Eligibility

Use `canMakePayment()` to check whether the customer's device can pay with Apple Pay. Razorpay's SDK encapsulates the device capability check, so you do not integrate the Apple Pay JS API or evaluate `paymentCredentialsAvailable` yourself.

```js: JavaScript
// canMakePayment() is async — call it inside an async function or a 
(async function () {
  var { available, reason } = await razorpay.canMakePayment({
    method: 'card',
    app: { name: 'apple_pay' },
  });
  // use `available` here — see step 1.5
})();
```

  
### canMakePayment Parameters

Parameter | Type | Required | Description
---
`method` | string | Yes | Payment method. Use `card`.
---
`app.name` | string | Yes | Name of the payment app. Use `apple_pay`.

    

The call resolves with `available: true` when the customer can pay with Apple Pay and `false` otherwise. Only render an Apple Pay button when `available` is `true`.

**INFO**

**Note on Eligibility**

`canMakePayment()` returns `true` for customers who can complete an Apple Pay payment on their current device and browser. For international customers, this includes devices where Apple Pay is set up and devices where the customer can add a card during the flow. For domestic (India) customers, it returns `true` only where a usable Apple Pay credential is already present. You do not need to handle these cases yourself — render the button whenever `available` is `true`.

### 1.5 Render the Button and Initiate Payment

Choose one of the following based on whether you want Razorpay to render the Apple Pay button or you render your own.

	

Use `mount()` to have Razorpay render an Apple Pay button into a container element you provide. The SDK starts the Apple Pay session on click and handles the payment — you do not call `createPayment()`.

```js: JavaScript
if (available) {
  razorpay.mount(
    {
      method: 'card',
      app: { name: 'apple_pay' },
      container: document.getElementById('apple-pay-container'),
      theme: {                          // optional design attributes
        themeColor: '#528FF0',
        buttonWidth: '300px',
        buttonHeight: '44px',
        buttonTheme: 'dark',
        buttonLabel: 'pay',
      },
    }
  );
}
```

  
### mount Parameters

Parameter | Type | Required | Default | Description
---
`method` | string | Yes | — | Payment method. Use `card`.
---
`app.name` | string | Yes | — | Payment app. Use `apple_pay`.
---
`container` | HTMLElement | Yes | — | The DOM element to mount the button into, for example `document.getElementById('apple-pay-container')`.
---
`theme.themeColor` | string | No | — | Hex colour for theming the DCC UI (for example, `#528FF0`).
---
`theme.buttonWidth` | string | No | `100px` | Button width — any valid CSS value.
---
`theme.buttonHeight` | string | No | `44px` | Button height — any valid CSS value.
---
`theme.buttonTheme` | string | No | `dark` | Button background. `dark` for dark background with light text, `light` for the reverse. *Apple Pay specific.*
---
`theme.buttonLabel` | string | No | `pay` | Button label. `pay`, `buy`, `plain`, `checkout`, `book`, `donate`, `order`.

    

	
	

Render your own Apple Pay button (using a Razorpay-provided button design — see Button Design Guidelines below), then call `createPayment()` inside the click handler. `createPayment()` must run inside a user-initiated event, as Apple Pay requires a direct user gesture to start a session.

```js: JavaScript
document.getElementById('my-apple-pay-btn').addEventListener('click', function () {
  razorpay.createPayment({
    method: 'card',
    app: { name: 'apple_pay' },
    order_id: 'order_XXXXXXXXXX',
    contact: '+919876543210',
    email: 'user@example.com',
  });
});
```

  
### createPayment Parameters

Parameter | Type | Required | Description
---
`method` | string | Yes | Payment method. Use `card`.
---
`app.name` | string | Yes | Payment app. Use `apple_pay`.
---
`order_id` | string | Yes | Order ID created in step 1.1.
---
`contact` | string | Optional | Customer phone number in E.164 format.
---
`email` | string | Optional | Customer email address.

    

	

### 1.6 Handle the Payment Response

Listen for payment lifecycle events, consistent with Custom Checkout. (You may also use the `handler` function from step 1.3.)

```js: JavaScript
razorpay.on('payment.success', function (response) {
  // response.razorpay_payment_id
  // response.razorpay_order_id
  // response.razorpay_signature   // verify on your server
});
 
razorpay.on('payment.error', function (response) {
  // response.error.code
  // response.error.description
  // response.error.reason
});
```

A successful payment returns:

```json: Response
{
  "razorpay_payment_id": "pay_29QQoUBi66xm2f",
  "razorpay_order_id": "order_9A33XWu170gUtm",
  "razorpay_signature": "9ef4dffbfd84f1318f6739a3ce19f9d85851857ae648f114332d8401e0949a3d"
}
```

Store these fields on your server and verify the payment signature (step 1.7).

A failed payment returns an error object:

```json: Response
{
  "error": {
    "code": "BAD_REQUEST_ERROR",
    "description": "Customer cancelled the Apple Pay sheet or did not authenticate in time.",
    "field": null,
    "source": "customer",
    "step": "payment_authentication",
    "reason": "payment_cancelled",
    "metadata": {
      "payment_id": "pay_EDNBKIP31Y4jl8",
      "order_id": "order_DBJKIP31Y4jl8",
      "method": "card",
      "app": "apple_pay"
    }
  }
}
```

For the full list of error responses — `canMakePayment()` reasons, payment errors, client errors and a handling guide — see [Error Responses](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/apple-pay/custom-integration/error-codes.md).

### 1.7 Verify the Payment Signature

Verify the signature on your server before fulfilling the order.

1. Use the `order_id` from your server (not the `razorpay_order_id` returned by Checkout), the `razorpay_payment_id` from the response and your `key_secret`.
2. Construct an HMAC SHA256 hex digest:

```js: JavaScript
generated_signature = hmac_sha256(order_id + "|" + razorpay_payment_id, secret);
 
if (generated_signature == razorpay_signature) {
    // payment is successful
}
```
3. If the generated signature matches `razorpay_signature`, the payment is authentic.

Sample verification (Node.js and other languages) is available in the [signature verification guide](https://razorpay.com/docs/build/llm-docs/payments/server-integration/nodejs/integration-steps.md).

### 1.8 Verify Payment Status

**INFO**

**Handy Tips**

On the Razorpay Dashboard, ensure the payment status is captured. See [capture settings](https://razorpay.com/docs/build/llm-docs/payments/payments/capture-settings.md) to capture payments automatically.

You can track payment status in three ways: from the Dashboard (**Transactions → Payments**), by subscribing to webhook events or by polling the APIs.

## Full Integration Example

```js: JavaScript
// SDK init — order created server-side at page load
var razorpay = new Razorpay({
  key: 'rzp_live_xxx',
  order_id: 'order_XXXXXXXXXX',
  contact: '9123456789',
  email: 'gaurav.kumar@example.com',
  handler: function (response) {
    // verify response.razorpay_signature on your server
  }
});

// Register event listeners before the async eligibility check
razorpay.on('payment.success', function (response) { /* store + verify */ });
razorpay.on('payment.error', function (response) { /* handle failure */ });

  var { available, reason } = await razorpay.canMakePayment({
    method: 'card',
    app: { name: 'apple_pay' },
  });

  if (available) {

    // Option A: Razorpay renders the button
    razorpay.mount({
      method: 'card',
      app: { name: 'apple_pay' },
      container: document.getElementById('apple-pay-container'),
      theme: {
        themeColor: '#528FF0',
        buttonTheme: 'dark',
        buttonLabel: 'pay',
      },
    });

    // Option B (alternative): you render your own button
    // document.getElementById('my-apple-pay-btn').style.display = 'block';
    // document.getElementById('my-apple-pay-btn').addEventListener('click', function () {
    //    razorpay.createPayment({
    //    order_id: 'order_XXXXXXXXXX'    
    //    method: 'card',
    //    app: { name: 'apple_pay' },
    //   });
    // });
  }
})();
```

## Frequently Asked Questions

  
### 1. Do I need to integrate the Apple Pay JS API myself?

No. `canMakePayment()` encapsulates the device capability check. You do not integrate the Apple Pay JS API or evaluate `paymentCredentialsAvailable` / `paymentCredentialStatusUnknown` yourself.

    

  
### 2. When should I show the Apple Pay button?

Render it only when `canMakePayment()` resolves with `available: true`.

    

  
### 3. Can the customer retry a failed payment?

Yes. On a retryable error (for example, `network_timeout`), retry with the same `order_id` — no duplicate payment is created until the previous attempt resolves.

    

  
### 4. Is it safe to create the order on the client side?

No. Always create orders server-side using your secret key. Only the `order_id` is passed to the frontend.

    

### Related Information

- [Apple Pay – Web Component Integration](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/apple-pay/custom-integration/web-sdk/web-component.md)
- [Apple Pay Integration – iOS (Custom Checkout)](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/apple-pay/ios-custom-checkout.md)
