---
title: WKWebView Integration
description: Integrate Apple Pay in iOS WKWebView using the Razorpay Web Component.
---

# WKWebView Integration

Apple Pay is supported inside WKWebView since iOS 11.3, but availability depends on the context in which the WebView is running.

   
### Where Apple Pay Works

       
       Context | Apple Pay Available?
       ---
       Safari (iOS / macOS) | Yes
       ---
       WKWebView in your own app with Apple Pay entitlement | Yes
       
       
**INFO**

**Best Practice: Apple Pay with iFrames**
As a best practice, if you want to show Apple Pay in an iframe element when the shopper is using Safari as their browser:
- For shoppers on Safari 17 later: add the `allow` attribute to the iframe to let the iframe communicate correctly with Apple Pay APIs:
` `
- Safari 17 is available on iOS 17 and later, and macOS 12 and later.
- For shoppers on Safari 16 or earlier: match the iframe origin and your top-level origin. The protocols, hosts (full domain name), and ports, when specified, must be the same for both pages.

      

 

   
### Where Apple Pay Does Not Work

       
       Context | Why
       ---
       SFSafariViewController | Apple explicitly blocks `ApplePaySession`.
       ---
       Chrome / Firefox on iOS | Uses WKWebView internally, but the Apple Pay entitlement is not passed through to web content.
       ---
       In-app browsers (Facebook, Instagram and so on.) | Third-party apps do not expose Apple Pay to embedded web content.
       ---
       UIWebView (deprecated) | No Apple Pay support.
       ---
       Cross-origin iframes (without `allow="payment"`) | `ApplePaySession` is unavailable unless the iframe has the `allow="payment"` attribute.
       
      

 

   
### Requirements for WKWebView

       For Apple Pay to work in your app's WKWebView, ensure the following:
 
       - **Apple Pay entitlement**: The host app must have `com.apple.developer.apple-pay` capability enabled in Xcode. Without this, `ApplePaySession` will be undefined in the WebView's JavaScript context.
       - **iOS 11.3+**: Minimum OS version for Apple Pay JS API version 3 in WKWebView.
       - **HTTPS**: The page loaded in the WebView must be served over HTTPS.
       - **Domain verification**: The domain served in the WebView must be registered and verified. Refer to the [Apple Pay Web Component Integration](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/apple-pay/web-component-integration.md) guide.
       - **Card in Apple Wallet**: The user must have at least one card added to Apple Wallet with face id, touch id or passcode enabled.
 
       
**INFO**

**Handy Tip**

There are no WebView-specific restrictions in this SDK. The same eligibility checks the device support, business configuration and card network availability, apply in both Safari and WKWebView. If all prerequisites above are met, Apple Pay will work in a WKWebView exactly as it does in Safari.

      

## Integrate in a Native iOS Checkout
 
If your app has a native checkout screen and you want to embed the Apple Pay button at a specific position and size, follow the steps given below.
 

   
### Step 1: Add Apple Pay Capability

       In Xcode, select your target → **Signing & Capabilities** → **+ Capability** → **Apple Pay**. Add your business identifier.
      

 

   
### Step 2: Host the Payment Page on Your Verified Domain

       Create a lightweight HTML page on the same domain you registered for Apple Pay verification. The app's WKWebView will load this URL directly, this ensures `window.location.hostname` matches your verified domain, which is required for business validation.
 
       ```
       https://your-domain.com/apple-pay.html
       ```
 
       ```html: HTML
       
       
       
           
           
           
               * { margin: 0; padding: 0; }
               body { background: transparent; overflow: hidden; }
           
       
       
           
       
       
       ```
 
       ```js: JavaScript
       // Read config from URL query params passed by the native app
       const params = new URLSearchParams(window.location.search);
       const wallet = document.getElementById('wallet');
       wallet.setAttribute('rzp-key', params.get('key'));
       wallet.setAttribute('order-id', params.get('order_id'));
       wallet.setAttribute('customer-contact-number', params.get('contact'));
       wallet.setAttribute('button-width', params.get('width') || '100%');
       wallet.setAttribute('button-height', params.get('height') || '44px');
 
       // Forward events to the native app via webkit message handler
       wallet.addEventListener('paymentsuccess', (e) => {
           webkit.messageHandlers.paymentEvent.postMessage({
               type: 'success',
               data: e.detail.paymentData
           });
       });
       wallet.addEventListener('paymentfailure', (e) => {
           webkit.messageHandlers.paymentEvent.postMessage({
               type: 'failure',
               data: e.detail.error
           });
       });
       wallet.addEventListener('error', (e) => {
           webkit.messageHandlers.paymentEvent.postMessage({
               type: 'error',
               data: { code: e.detail.errorCode, message: e.detail.message }
           });
       });
       ```
 
       The page reads `key`, `order_id`, `contact`, `width` and `height` from query parameters, so the native app controls all configuration without changing the hosted HTML.
      

 

   
### Step 3: Create a WKWebView and Load the Hosted Page

 
       ```bash: Bash
       import UIKit
       import WebKit
 
       class CheckoutViewController: UIViewController, WKScriptMessageHandler {
           private var applePayWebView: WKWebView!
 
           // Button size in points — the WebView frame and the component stay in sync
           private let buttonWidth: CGFloat = 300
           private let buttonHeight: CGFloat = 44
 
           override func viewDidLoad() {
               super.viewDidLoad()
 
               let config = WKWebViewConfiguration()
               config.preferences.javaScriptEnabled = true
               config.userContentController.add(self, name: "paymentEvent")
 
               applePayWebView = WKWebView(
                   frame: CGRect(x: 0, y: 0, width: buttonWidth, height: buttonHeight),
                   configuration: config
               )
               applePayWebView.scrollView.isScrollEnabled = false
               applePayWebView.isOpaque = false
               applePayWebView.backgroundColor = .clear
               applePayWebView.scrollView.backgroundColor = .clear
 
               // Position it within your native checkout layout
               view.addSubview(applePayWebView)
 
               loadApplePayButton(
                   rzpKey: "rzp_test_<REDACTED>",
                   orderId: "order_XXXXXXXXXX", // created via your server
                   contact: "+919876543210"
               )
           }
 
           private func loadApplePayButton(rzpKey: String, orderId: String, contact: String) {
               var components = URLComponents(string: "https://your-domain.com/apple-pay.html")!
               components.queryItems = [
                   URLQueryItem(name: "key", value: rzpKey),
                   URLQueryItem(name: "order_id", value: orderId),
                   URLQueryItem(name: "contact", value: contact),
                   URLQueryItem(name: "width", value: "\(Int(buttonWidth))px"),
                   URLQueryItem(name: "height", value: "\(Int(buttonHeight))px"),
               ]
               applePayWebView.load(URLRequest(url: components.url!))
           }
 
           func userContentController(
               _ userContentController: WKUserContentController,
               didReceive message: WKScriptMessage
           ) {
               guard let body = message.body as? [String: Any],
                     let type = body["type"] as? String,
                     let data = body["data"] as? [String: Any] else { return }
 
               switch type {
               case "success":
                   let paymentId = data["razorpay_payment_id"] as? String ?? ""
                   let orderId = data["razorpay_order_id"] as? String ?? ""
                   let signature = data["razorpay_signature"] as? String ?? ""
                   // Always verify signature on your server before fulfilling the order
                   handlePaymentSuccess(paymentId: paymentId, orderId: orderId, signature: signature)
               case "failure":
                   let code = data["code"] as? String ?? ""
                   let message = data["message"] as? String ?? ""
                   if code == "PAYMENT_CANCELLED" {
                       handlePaymentCancelled()
                   } else {
                       handlePaymentFailure(code: code, message: message)
                   }
               case "error":
                   let message = data["message"] as? String ?? ""
                   handleComponentError(message: message)
               default:
                   break
               }
           }
       }
       ```
      

 

   
### Sizing

       The button size is controlled in two places, keep them in sync:
 
       
       Where | What to Set
       ---
       Native side | WKWebView frame (for example, `CGRect(x:y:width:300, height:44)`)
       ---
       Query params | `width` and `height` (for example, `300px`, `44px`) applied to `button-width` and `button-height` attributes
       
 
       The WebView acts as a transparent window into your native layout. Set `isOpaque = false` and `backgroundColor = .clear` so only the Apple Pay button is visible.
      

 

   
### Why Host the Page Instead of Using Inline HTML?

       The SDK sends `window.location.hostname` as the `initiativeContextUrl` during Apple Pay business validation. When HTML is loaded via `loadHTMLString`, the hostname may not match your verified domain, causing business validation to fail. Loading a real URL on your verified domain avoids this entirely.
      

### Related Information
 
[Apple Pay Web Component Integration](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/apple-pay/web-component-integration.md)
