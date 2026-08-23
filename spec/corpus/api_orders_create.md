---
title: Create an Order
description: Create an Order using Razorpay Orders API.
---

# Create an Order

**POST** `/v1/orders`

Use this endpoint to create an order with basic details such as amount and currency.

**WARN**

**Watch Out: Create a new order for every payment attempt**

A Razorpay Order ID maps 1:1 to a payment attempt. If a customer's payment fails and they try again, you must create a new Order on your server and pass the new `order_id` to Checkout. Reusing the previous order ID will cause an error.

### Request

```curl: Curl
curl -u [YOUR_KEY_ID]:[YOUR_KEY_SECRET] \
-X POST https://api.razorpay.com/v1/orders \
-H "content-type: application/json" \
-d '{
  "amount": 5000,
  "currency": "INR",
  "receipt": "receipt#1",
  "notes": {
    "key1": "value3",
    "key2": "value2"
  }
}'

```java: Java
RazorpayClient razorpay = new RazorpayClient("[YOUR_KEY_ID]", "[YOUR_KEY_SECRET]");

JSONObject orderRequest = new JSONObject();
orderRequest.put("amount",5000);
orderRequest.put("currency","INR");
orderRequest.put("receipt", "receipt#1");
JSONObject notes = new JSONObject();
notes.put("notes_key_1","Tea, Earl Grey, Hot");
notes.put("notes_key_1","Tea, Earl Grey, Hot");
orderRequest.put("notes",notes);

Order order = razorpay.orders.create(orderRequest);

```Python: Python
import razorpay
client = razorpay.Client(auth=("YOUR_ID", "YOUR_SECRET"))

client.order.create({
  "amount": 5000,
  "currency": "INR",
  "receipt": "receipt#1",
  "notes": {
    "key1": "value3",
    "key2": "value2"
  }
})

```php: PHP
$api = new Api($key_id, $secret);

$$api->order->create(array('receipt' => '123', 'amount' => 100, 'currency' => 'INR', 'notes'=> array('key1'=> 'value3','key2'=> 'value2')));

```csharp: .NET
RazorpayClient client = new RazorpayClient("[YOUR_KEY_ID]", "[YOUR_KEY_SECRET]");

Dictionary options = new Dictionary();
options.Add("amount", 5000); // amount in the smallest currency unit
options.Add("receipt", "order_rcptid_11");
options.Add("currency", "INR");
Order order = client.Order.Create(options);

```ruby: Ruby
require "razorpay"
Razorpay.setup('YOUR_KEY_ID', 'YOUR_SECRET')

para_attr = {
  "amount": 5000,
  "currency": "INR",
  "receipt": "receipt#1",
  "notes": {
    "key1": "value3",
    "key2": "value2"
  }
}

Razorpay::Order.create(para_attr)

```javascript: Node.js
var instance = new Razorpay({ key_id: 'YOUR_KEY_ID', key_secret: 'YOUR_SECRET' })

instance.orders.create({
  amount: 50000,
  currency: "INR",
  receipt: "receipt#1",
  notes: {
    key1: "value3",
    key2: "value2"
  }
})

```go: Go
import ( razorpay "github.com/razorpay/razorpay-go" )
client := razorpay.NewClient("YOUR_KEY_ID", "YOUR_SECRET")

data := map[string]interface{}{
  "amount": 5000,
  "currency": "INR",
  "receipt": "some_receipt_id",
  "partial_payment": false,
  "notes": map[string]interface{}{
      "key1": "value1",
      "key2": "value2",
    } 
}
body, err := client.Order.Create(data, nil)

```bash: CLI
razorpay orders create \
  --amount 50000 \
  --currency INR \
  --receipt "receipt#001" \
  --note key1="Beam me up Scotty"
```

### Response

```json: Success
{
  "amount": 5000,
  "amount_due": 5000,
  "amount_paid": 0,
  "attempts": 0,
  "created_at": 1756455561,
  "currency": "INR",
  "entity": "order",
  "id": "order_RB58MiP5SPFYyM",
  "notes": {
      "key1": "value3",
      "key2": "value2"
  },
  "offer_id": null,
  "receipt": "receipt#1",
  "status": "created"
}

```json: Failure
{
  "error": {
    "code": "BAD_REQUEST_ERROR",
    "description": "The amount must be at least INR 1.00",
    "source": "business",
    "step": "payment_initiation",
    "reason": "input_validation_failed",
    "metadata": {},
    "field": "amount"
  }
}
```

**WARN**

**Watch Out: Always verify the payment signature server-side**

After a payment completes, Razorpay sends `razorpay_payment_id`, `razorpay_order_id` and `razorpay_signature` to your handler. You must verify the signature on your server before fulfilling the order.

Skipping this step means anyone can fake a successful payment by sending a POST request to your callback. This is the most common cause of payment disputes and fraudulent orders.

### Parameters

`amount` _mandatory_
: `integer` Payment amount in the smallest currency sub-unit. For example, if the amount to be charged is , then pass `29900` in this field. In the case of three decimal currencies, such as KWD, BHD and OMR, to accept a payment of 295.991, pass the value as `295990`. And in the case of zero decimal currencies such as JPY, to accept a payment of 295, pass the value as `295`.

  
**WARN**

**Watch Out!**

As per payment guidelines, you should pass the last decimal number as 0 for three decimal currency payments. For example, if you want to charge a customer 99.991 KD for a transaction, you should pass the value for the amount parameter as `99990` and not `99991`.

`currency` _mandatory_
: `string` ISO code for the currency in which you want to accept the payment. The default length is 3 characters. Refer to the [list of supported currencies](https://razorpay.com/docs/build/llm-docs/payments/international-payments.md#supported-currencies).

  
**INFO**

**Handy Tips**

Razorpay has added support for zero decimal currencies, such as JPY, and three decimal currencies, such as KWD, BHD, and OMR, allowing businesses to accept international payments in these currencies. Know more about [Currency Conversion](https://razorpay.com/docs/build/llm-docs/payments/international-payments/currency-conversion.md) (May 2024).

`receipt` _optional_
: `string` Receipt number that corresponds to this order, set for your internal reference. Can have a maximum length of 40 characters and has to be unique.

`notes` _optional_
: `json object` Key-value pair that can be used to store additional information about the entity. Maximum 15 key-value pairs, 256 characters (maximum) each. For example, `"note_key": "Beam me up Scotty”`.

### Parameters

`id`
: `string` The unique identifier of the order.

`amount`
: `integer` The amount for which the order was created, in currency subunits. For example, for an amount of , enter `29500`.

`entity`
: `string` Name of the entity. Here, it is `order`.

`amount_paid`
: `integer` The amount paid against the order.

`amount_due`
: `integer` The amount pending against the order.

`currency`
: `string` ISO code for the currency in which you want to accept the payment. The default length is 3 characters.

`receipt`
: `string` Receipt number that corresponds to this order. Can have a maximum length of 40 characters and has to be unique.

`status`
: `string` The status of the order. Possible values:
   - `created`: When you create an order it is in the `created` state. It stays in this state till a payment is attempted on it.
   - `attempted`: An order moves from `created` to `attempted` state when a payment is first attempted on it. It remains in the `attempted` state till one payment associated with that order is captured.
   - `paid`: After the successful capture of the payment, the order moves to the `paid` state. No further payment requests are permitted once the order moves to the `paid` state. The order stays in the `paid` state even if the payment associated with the order is refunded.

`attempts`
: `integer` The number of payment attempts, successful and failed, that have been made against this order.

`notes`
: `json object` Key-value pair that can be used to store additional information about the entity. Maximum 15 key-value pairs, 256 characters (maximum) each. For example, `"note_key": "Beam me up Scotty”`.

`created_at`
: `integer` Indicates the Unix timestamp when this order was created.

`offer_id`
: `string` Unique identifier of the offer associated with this order.

### Errors

Authentication failed.
* code: 400
* description: The API credentials passed in the API call differ from the ones generated on the Dashboard. Possible reasons: - Different keys for test mode and live modes.
- Expired API key.

* solution: The API keys must be active and entered correctly with no whitespace before or after the keys.

The amount must be at least INR 1.00.
* code: 400
* description: The amount specified is less than the minimum amount. Currency subunits, such as paise (in the case of INR), should always be greater than 100.
* solution: Enter an amount equal to or greater than the minimum amount, that is 100.

The **field name** is required.
* code: 400
* description: A mandatory field is missing.
* solution: Ensure all mandatory fields and values are present.

amount: must be no less than 0.
* code: 400
* description: A negative `amount` was sent in the request body.
* solution: `amount` must be a non-negative integer.

The amount must be an integer.
* code: 400
* description: `amount` was sent as a string, float or other non-integer type.
* solution: Pass `amount` as a JSON integer (for example, `100`, not `"100"` or `100.0`).

Amount exceeds maximum amount allowed.
* code: 400
* description: `amount` exceeds the per-order maximum configured for the account or currency.
* solution: Check your account-level transaction limit. For large orders, split into multiple smaller orders or contact Razorpay support to raise the limit.

currency: validation_failure: BAD_REQUEST_INVALID_CURRENCY.
* code: 400
* description: An unsupported `currency` value was sent (for example, `XYZ`) or a currency that is not enabled for your account.
* solution: Use a supported ISO-4217 currency code. To accept currencies other than your default, enable **International payments** under **Account & Settings** on the Razorpay Dashboard.

receipt: the length must be no more than 40.
* code: 400
* description: `receipt` value exceeds 40 characters.
* solution: Keep `receipt` to 40 characters or fewer. Use an internal short id or hash if your reference is longer.

The receipt: validation_failure: BAD_REQUEST_ENCODING_VALIDATION_FAILED.
* code: 400
* description: `receipt` contains characters outside the supported encoding (for example, emoji or non-ASCII characters).
* solution: Use only ASCII characters in `receipt`. Restrict to alphanumerics, underscores and hyphens for maximum compatibility.

first_payment_min_amount should be greater than or equal to 0.
* code: 400
* description: `first_payment_min_amount` was set to a negative value while `partial_payment: true`.
* solution: Use a `first_payment_min_amount` that is greater than or equal to 0 and less than or equal to `amount`.

EOF.
* code: 400
* description: The request body is malformed JSON. It may be truncated, missing a closing brace or otherwise unparseable.
* solution: Ensure the request body is valid JSON. Validate locally with `jq .` or a JSON linter before sending.

Duplicate request. This request has already been processed.
* code: 400
* description: An order with the same `receipt` value has already been created on this account. `receipt` is treated as an idempotency key, so a second create call with the same value is rejected.
* solution: Use a unique value for `receipt` on every order, or fetch the existing order created with the same receipt and reuse it.

Request failed because another order operation is in progress.
* code: 400
* description: A concurrent create or update is already running against this order. Razorpay locks the order to prevent state corruption.
* solution: Wait a few seconds and retry. If the issue persists, fetch the order to confirm its current state before retrying.

Bank code provided is invalid.
* code: 400
* description: For TPV (third-party validation) orders, the `bank` value passed is not a recognised IFSC bank code.
* solution: Pass a valid 4-letter bank code (for example, `HDFC`, `ICIC`). See the supported bank codes in the Razorpay Dashboard.

The requested bank is not enabled for the merchant.
* code: 400
* description: For TPV orders, the `bank` passed is valid but not enabled on your account.
* solution: Contact Razorpay support to enable the requested bank for your account, or pass a bank that is already enabled.

Bank code should be provided in input if account number is sent.
* code: 400
* description: For TPV orders, an `account_number` was passed without the accompanying `bank` field.
* solution: Always pass `bank` alongside `account_number` for TPV orders.

Account number is mandatory for this merchant.
* code: 400
* description: Your account is configured to require an `account_number` on every order (TPV-enforced merchants), but the field is missing from the request.
* solution: Include `account_number` in the order create request.
