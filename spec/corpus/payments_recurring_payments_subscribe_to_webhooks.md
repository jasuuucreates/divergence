---
title: Webhooks
description: Configure Webhooks to receive alerts about the status of tokens and recurring payments as they occur.
---

# Webhooks

You can use Razorpay [Webhooks](https://razorpay.com/docs/build/llm-docs/webhooks.md) to receive notifications of all events related to payment states and the token in the recurring payments workflow.

## Check Payment Status Using Webhooks

You can [set up Webhooks](https://razorpay.com/docs/build/llm-docs/api/payments/recurring-payments/webhooks.md#setup-webhooks) to get notifications about the following:
- [Authorisation payment states](#authorisation-payment-states)
- [Registration link states for recurring payments](#registration-link-states)
- [Token states](#token-states)

### Authorisation Payment States

Once the customer has made the Authorisation Payment, it moves through the following states as per the [payment flow](https://razorpay.com/docs/build/llm-docs/payments/payment-gateway/how-it-works.md):

Status | Description | Webhook
---
Created | Payment is created when a customer enters and submits the payment information. | NA
---
Authorized | Payment is authorized when the customer’s payment details are successfully authenticated by the bank. | [payment.authorized](https://razorpay.com/docs/build/llm-docs/api/payments/recurring-payments/webhooks.md#payment-authorized)
---
Captured | Indicates that the payment is verified by you.
Once a payment is captured you can [retrieve the token](https://razorpay.com/docs/build/llm-docs/payments/recurring-payments/create.md#3-search-for-the-token). | [payment.captured](https://razorpay.com/docs/build/llm-docs/api/payments/recurring-payments/webhooks.md#payment-captured) or [order.paid](https://razorpay.com/docs/build/llm-docs/api/payments/recurring-payments/webhooks.md#order-paid)
---
Failed | Indicates that the payment has failed.
If the payment has failed, you need to [create an authorisation transaction](https://razorpay.com/docs/build/llm-docs/api/payments/recurring-payments/cards/create-authorization-transaction.md) again. | [payment.failed](https://razorpay.com/docs/build/llm-docs/api/payments/recurring-payments/webhooks.md#payment-failed)

### Registration Link States

A registration link moves through the following states during its life cycle:

Status | Description | Webhook
---
Issued | A registration Link is created and sent to the customer. | NA
---
Paid | Payment is made for the issued registration Link.
Once the registration Link is paid, search for Token corresponding to the payment. | [invoice.paid](https://razorpay.com/docs/build/llm-docs/api/payments/recurring-payments/webhooks.md#invoice-paid)
---
Cancelled | The registration link has been canceled. In such cases, you need to create a registration link again.| NA
---
Expired | The registration link has expired. You can set an expiry timestamp at the time of creation. | [invoice.expired](https://razorpay.com/docs/build/llm-docs/api/payments/recurring-payments/webhooks.md#invoice-expired)

### Token States

`token_status` | Description | Next Step
---
`initiated` | Indicates that the bank is processing the mandate registration. | Wait for the [token.confirmed](https://razorpay.com/docs/build/llm-docs/api/payments/recurring-payments/webhooks.md#token-confirmed) webhook.
---
`confirmed` | Indicates that the bank has completed the mandate registration. | [Create recurring payment](https://razorpay.com/docs/build/llm-docs/payments/recurring-payments/create.md)
---
`rejected` | Indicates that the mandate registration has failed. | Create the authorisation transaction again.
---
`cancelled` | Indicates that the token has been cancelled. | Create the authorisation transaction again if you want to charge the customer.
---
`paused` | Indicates that the token has been paused by your customer. | The token is inactive. Your customer has paused the token. Ask them to resume the token to charge them.

## Sample Payloads

Know more about the [Webhook payloads](https://razorpay.com/docs/build/llm-docs/api/payments/recurring-payments/webhooks.md#sample-payloads).

### Related Information

- [Emandate](https://razorpay.com/docs/build/llm-docs/payments/recurring-payments/emandate/integrate.md)
- [Cards](https://razorpay.com/docs/build/llm-docs/payments/recurring-payments/cards/integrate.md)
- [Paper NACH](https://razorpay.com/docs/build/llm-docs/payments/recurring-payments/paper-nach/integrate.md)
- [UPI](https://razorpay.com/docs/build/llm-docs/payments/recurring-payments/upi/integrate.md)
