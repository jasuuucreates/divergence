---
title: Web Component Integration
description: Embed Apple Pay directly on your checkout page using the Razorpay `<razorpay-checkout>` component for a fully customised payment experience.
---

# Web Component Integration

Apple Pay Component integration lets you embed the Apple Pay button directly on your checkout page using the `` web component. This gives you full control over button placement and styling while Razorpay handles the underlying payment flow. The component is part of Razorpay Custom Checkout, so existing Custom Checkout merchants do not need to load any additional script. Know more about [Apple Pay](https://www.apple.com/apple-pay/).

    
### Advantages

         Integrating Apple Pay using the Component method offers you the following advantages:

         - **Customisable appearance**: Configure the button theme, label, width and height to match your brand using the component attributes.
         - **Reduced friction**: Eliminate manual card entry with biometric authentication (Face ID/Touch ID).
         - **Enhanced security**: Benefit from Apple's tokenisation and Razorpay signature verification.
         - **Device-aware rendering**: The component automatically checks device eligibility and only renders the button when Apple Pay is supported — no additional logic required on your end.
         - **Seamless event handling**: Built-in events for payment success, failure and component errors integrate directly with your existing checkout logic.
         - **No extra script for existing merchants**: The component ships with the Custom Checkout script you already use.
        

## Prerequisites

Before starting the integration, ensure you have the following:

- A Razorpay account with Apple Pay enabled.
   - Log in to the [Razorpay Dashboard](https://dashboard.razorpay.com/app/payment-methods/apple-pay).
   - Navigate to **Account & Settings** → **Payment Methods** → **Apple Pay**.
- An existing Razorpay Custom Checkout integration.
- International Payments enabled on your Razorpay account.
- Your API Key Id available. Know how to generate [API Keys from the Dashboard](https://razorpay.com/docs/build/llm-docs/payments/dashboard/account-settings/api-keys.md#generate-api-keys).
- An HTTPS-enabled domain (TLS 1.2 or higher). Apple Pay requires a secure context and will not function over HTTP.
- Server-side capability to create orders via the Razorpay Orders API.
- A compatible device or browser for testing: Safari on iOS 10+ / macOS Sierra+ or Chrome/Edge with Apple Pay configured in Wallet.
- Apple Pay domain verification completed for your checkout domain (covered in Step 1 below).

## Integrate Apple Pay via Component

Follow the steps given below.

   
### Step 1: Domain Verification

       Before Apple Pay can render on your domain, you must host a domain association file and register the domain with Razorpay.

       
**WARN**

**Watch Out!**

- The file path is case-sensitive and must be exact.
- The file must be served over HTTPS and return a direct HTTP 200 response. Redirects (301/302) will cause verification to fail.
- The file must be publicly accessible — no authentication, no proxy and no password protection.
- If you are using a CDN, purge the cache after deploying or updating the file.

       **Domain Verification Process**

       1. **Download the domain association file.**
          1. Log in to the [Razorpay Dashboard](https://dashboard.razorpay.com/app/payment-methods/apple-pay).
          2. Navigate to **Account & Settings** → **Payment Methods** → **Apple Pay**.
          3. Download the `apple-developer-merchantid-domain-association` file.

       2. **Host the file on your server at the exact path below:**
          ```
          /.well-known/apple-developer-merchantid-domain-association
          ```
          For example, if your domain is `https://www.yourstorename.com`, the file must be accessible at:
          ```
          https://www.yourstorename.com/.well-known/apple-developer-merchantid-domain-association
          ```

       3. **Ensure correct server configuration:**

          - The file must return HTTP 200 — no 301, 302 or any other 3xx redirects.
          - The URL must not contain a trailing slash.
          - Serve the file with `Content-Type: text/plain` or `application/octet-stream`.
          - The file must not be behind authentication or a proxy.

          For example, Nginx:
          ```bash: Bash
          location /.well-known/apple-developer-merchantid-domain-association {
              default_type application/octet-stream;
          }
          ```

          For example, Express (Node.js):
          ```js: JavaScript
          app.use('/.well-known', express.static(path.join(__dirname, '.well-known')));
          ```

       4. **Verify the file is accessible.**
          Visit the URL in your browser and confirm you see the file content (a hex string). If you see a 404, redirect or login page, fix the hosting configuration before proceeding.

       5. **Register the domain in the Razorpay Dashboard.**
          1. Go to **Account & Settings** → **Payment Methods** → **Apple Pay**.
          2. Enter your domain (for example, `merchant-website.com`).
          3. Click **Verify**. Razorpay will confirm the file is accessible at the expected URL.
          4. Domain status changes to **Verified** once the file is correctly configured.

       **Domain Verification Troubleshooting**

       
       Issue | Fix
       ---
       404 Not Found | Ensure the `.well-known/` directory exists at your domain root and the file is deployed.
       ---
       Redirect (301/302) | Apple's verification rejects redirects. Serve the file directly at the exact path.
       ---
       CDN caching old content | Purge your CDN cache after deploying or updating the file.
       ---
       Wrong Content-Type | Configure your server to serve the file as `text/plain` or `application/octet-stream`.
       ---
       Authentication required | The file must be publicly accessible — no login, no Basic Auth.
       ---
       Trailing slash in URL | The URL must not end with a trailing slash.
       

      

   
### Step 2: Add the Razorpay Script

       Include the Razorpay Custom Checkout script in your page's `` tag. This is the same script used for Custom Checkout; it registers the `` web component and makes it available for use in your HTML.

       ```html: HTML
       
           
       
       ```

       
**INFO**

**Handy Tip**

Load this script on every page where you intend to render the Apple Pay button. The script must be loaded before the `` component is placed in the DOM. Existing Custom Checkout merchants already load this script and do not need to add a new one.

      

   
### Step 3: Create an Order on Your Server

       You must create a Razorpay order on your server before rendering the Apple Pay button. The `order_id` returned from this call is passed directly to the web component.

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

       The response includes an `id` field (for example, `order_XXXXXXXXXX`). Pass this value to your frontend to use as the `order-id` attribute on the component.

       The parameter descriptions and errors are present in the [Create an Order API](https://razorpay.com/docs/build/llm-docs/api/orders/create.md).
      

   
### Step 4: Render the Component and Handle Events

       Place the `` component in your HTML at the exact location where you want the Apple Pay button to render. The button loads inline at the position of this component. Attach event listeners to handle the payment outcome.

       ```html: HTML
       
       ```

       To customise the button appearance, add the optional design attributes:

       ```html: HTML
       
       ```

       Attach event listeners to the component:

       ```js: JavaScript
       const checkout = document.querySelector('razorpay-checkout');
        
       checkout.addEventListener('payment.success', (e) => {
           const { razorpay_payment_id, razorpay_order_id, razorpay_signature } = e.detail.paymentData;
           // Send these to your server for signature verification
       });
        
       checkout.addEventListener('payment.failure', (e) => {
           console.error('Payment failed:', e.detail.error.message);
       });
        
       checkout.addEventListener('error', (e) => {
           console.error('Component error:', e.detail.message);
       });
       ```

       
**INFO**

**Handy Tip**

The component checks device eligibility on mount and renders the Apple Pay button only if the customer's device supports it. If Apple Pay is not available, nothing is rendered — no additional conditional logic is needed on your end.

       **React 19 Example**

React 19 has native custom element support, so event handlers work directly on the `` component.

   
      React 19 Implementation
      

       
**WARN**

**Watch Out! — React and the `key` attribute**

`key` is a reserved React prop for list reconciliation and is **never forwarded to the DOM element**. Passing `key={rzpKey}` on `` will silently do nothing in any React version. Use a `ref` and set the attribute imperatively instead — as shown below.

       ```js: JavaScript
       // React 19+ — event handlers work directly on custom elements.
       // For React 18 and below, also use a ref for event listeners:
       // e.g. ref.current.addEventListener('payment.success', handler)
       import { useRef, useEffect } from 'react';

       function Checkout({ rzpKey, orderId }) {
         const ref = useRef(null);

         useEffect(() => {
           // `key` is reserved by React and not forwarded to the DOM.
           // Set it via the DOM API instead.
           if (ref.current) {
             ref.current.setAttribute('key', rzpKey);
           }
         }, [rzpKey]);

         function handleSuccess(e) {
           const { razorpay_payment_id, razorpay_order_id, razorpay_signature } = e.detail.paymentData;
           // Send to your server for verification
         }

         function handleFailure(e) {
           const { code, message } = e.detail.error;
           // Handle failure or cancellation
         }

         function handleError(e) {
           console.error('Component error:', e.detail.message);
         }

         return (
           
             
           
         );
       }
       ```
      

      
   
   
### Step 5: Verify the Payment Signature on Your Server

       After a successful payment (the `payment.success` event fires), verify the payment signature on your server before fulfilling the order.

       Send the following fields to your backend:
       - `razorpay_payment_id`
       - `razorpay_order_id`
       - `razorpay_signature`

       Verify them using the standard [Razorpay signature verification process](https://razorpay.com/docs/build/llm-docs/payments/server-integration/python/integration-steps.md#14-verify-payment-signature).

       
**WARN**

**Watch Out!**

Never fulfil an order based solely on the client-side `payment.success` event. Signature verification ensures the payment was genuinely processed by Razorpay and has not been tampered with.

      

## Component Reference

 
### Attributes

Attribute | Type | Required | Default | Description
---
`key` | string | Yes | — | Your Razorpay key id (`rzp_test_*` or `rzp_live_*`). **React users**: see the React 19 example above — `key` is a reserved React prop and must be set via a `ref`.
---
`order-id` | string | Yes | — | Razorpay order id created server-side (for example, `order_XXXXXXXXXX`).
---
`contact` | string | Yes | — | Customer's phone number in E.164 format (for example, `+919876543210`). Required by the component at mount time. (In the Headless SDK's `createPayment()`, `contact` is optional.)
---
`email` | string | No | — | Customer's email address (for example, `user@example.com`). Recommended for payment confirmation and dispute resolution.
---
`method` | string | Yes | — | Payment method. Use `card`.
---
`app-name` | string | Yes | — | Name of the payment app. Use `apple_pay`.
---
`theme-color` | string | No | — | Hex colour for theming the DCC UI (for example, `#528FF0`), shown when Dynamic Currency Conversion is applicable.
---
`button-width` | string | No | `100px` | Button width — any valid CSS value (for example, `300px`).
---
`button-height` | string | No | `44px` | Button height — any valid CSS value (for example, `44px`).
---
`button-theme` | string | No | `dark` | Button background. `dark` for dark background with light text, `light` for light background with dark text. *Apple Pay specific.*
---
`button-label` | string | No | `pay` | Button label. `pay` renders "Pay with Apple Pay". Other values: `buy`, `plain`, `checkout`, `book`, `donate`, `order`.

**INFO**

**Note**

Attributes use kebab-case to match common HTML/CSS conventions and to avoid clashes with JavaScript objects.

  

### Events

   
### payment.success

       Fired when the payment completes successfully. The event detail contains:

       ```js: JavaScript
       {
           status: 'success',
           paymentData: {
               razorpay_payment_id: string,
               razorpay_order_id: string,
               razorpay_signature: string
           }
       }
       ```

       Use these three values to verify the payment on your server before fulfilling the order.
      

   
### payment.failure

       Fired when the payment fails or the customer cancels the payment sheet.

       ```js: JavaScript
       {
           status: 'failure',
           error: {
               code: 'PAYMENT_CANCELLED' | 'PAYMENT_FAILED' | 'INTERNAL_ERROR',
               reason: string,
               message: string
           }
       }
       ```

       
       Code | When
       ---
       `PAYMENT_CANCELLED` | Customer dismissed the Apple Pay payment sheet
       ---
       `PAYMENT_FAILED` | Payment could not be completed
       ---
       `INTERNAL_ERROR` | An unexpected error occurred
       
      

   
### error

       Fired if the component fails to initialise — for example, due to an invalid attribute or Apple Pay not being enabled for your business account.

       ```js: JavaScript
       {
           errorCode: string,
           message: string
       }
       ```

       Check that `key`, `order-id`, `method` and `app-name` are all correctly set if you receive this event on load.
      

## Testing

   
### Testing on Real Apple Devices

       To test the full payment flow on Apple hardware:

       - Use your `rzp_test_*` key. Test payments will not charge real money.
       - Use a real Apple device (iPhone, iPad or Mac) with Apple Pay configured in the Wallet app.
       - Add a sandbox Apple Pay card via the Wallet app using an Apple sandbox tester account.
       - Supported test card numbers are listed in [Apple's sandbox testing documentation](https://developer.apple.com/apple-pay/sandbox-testing/).
      

   
### Go-live Checklist

       Before launching Apple Pay on your live site, confirm the following:

       - The Apple Pay button appears correctly on supported devices.
       - The button does **not** appear on unsupported devices or browsers.
       - Clicking the button opens the Apple Pay payment sheet as expected.
       - Completing a payment fires `payment.success` with valid `razorpay_payment_id`, `razorpay_order_id` and `razorpay_signature`.
       - Cancelling the payment sheet fires `payment.failure` with code `PAYMENT_CANCELLED`.
       - Server-side signature verification succeeds for completed payments.
       - The `error` event does not fire on component load in your production environment.
      

**INFO**

**Best Practice: Apple Pay with iFrames**

As a best practice, if you want to show Apple Pay in an iframe element when the shopper is using Safari as their browser:

- For shoppers on Safari 17 and later: add the `allow` attribute to the iframe to let the iframe communicate correctly with Apple Pay APIs:
``
- Safari 17 is available on iOS 17 and later and macOS 12 and later.
- For shoppers on Safari 16 or earlier: match the iframe origin and your top-level origin. The protocols, hosts (full domain name) and ports, when specified, must be the same for both pages.

## Frequently Asked Questions

   
### 1. Why is the Apple Pay button not appearing on my checkout page?

       - Domain verification has not been completed or the association file is no longer accessible.
       - The customer's device or browser does not support Apple Pay.
       - Apple Pay is not enabled on your Razorpay account.
       - The `key`, `order-id`, `method` or `app-name` attribute on the component is missing or invalid — check for the `error` event firing on load.
      

   
### 2. Why is my Apple Pay domain verification failing in the Dashboard?

       - The verification file is not returning HTTP 200 — check for 301 or 302 redirects.
       - The file path is not exactly `/.well-known/apple-developer-merchantid-domain-association` (case-sensitive).
       - The file is not accessible over HTTPS.
       - A CDN is serving a cached or incorrect version — purge your CDN cache and retry.
       - The file requires authentication or is behind a proxy.
      

   
### 3. The Apple Pay button appears but the payment sheet does not open. What should I do?

       This typically indicates that domain verification has expired or the association file has been removed from your server. Verify that the file is still accessible at the exact URL and re-verify the domain in the Razorpay Dashboard if necessary.
      

   
### 4. Is it safe to create the Razorpay order on the client side?

       No. Orders must always be created server-side using your secret API key. Never expose your secret key in client-side code. Only the `order_id` (not the secret key) should be passed to the frontend and used as the `order-id` attribute on the component.
      

### Related Information

- [Apple Pay – Custom Checkout (Headless)](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/apple-pay/custom-integration.md)
- [Apple Pay WKWebView Integration](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/apple-pay/wkwebview-integration.md)
