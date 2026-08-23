---
title: Normal Refunds
description: Check how to issue Normal Refunds to your customers, the refund process, processing time and refund fees.
---

# Normal Refunds

You can issue Normal refunds to your customers which are processed within 7-10 working days.

**INFO**

**Customer Looking for Refund**

If you are a customer looking for a refund, know more about [customer refunds](https://razorpay.com/docs/build/llm-docs/payments/customers/customer-refunds.md).

## How Normal Refunds Work

When you make a Normal refund request to Razorpay, the information is sent to banking partners or other related stakeholders. Each of them have their own process for refund requests. After processing the refund request, the refund amount is sent to the customer's bank account or card balance.

Following is a typical flow for card refunds:

### Payment Methods

We support all payment methods for Normal refunds.

Refunds are sent back to the original payment method used in making the payment. For example, if a credit card was used to make the payment, the refund amount is pushed to the same credit card.

### Processing Time

When you send a Normal refund request to Razorpay, the information is sent to our banking partners. Depending on the bank's processing time, it can take 7-10 business days for the refunds to reflect in the customer's bank account or card balance.

The time taken to process a normal refund depends on the payment mode used while making the payment.

**Payment Method** | **Refund Time**
---
`credit` or `debit` cards | 5-10 days
---
`netbanking` | 2-10 days
---
`wallet` | 0-3 days
---
`upi` | 2-7 days

### Refund Fees

For Normal refunds, Razorpay does not charge any processing fee. However, the transaction fee and GST levied by Razorpay at the time of payment capture will not be reversed to your account (merchant's account).

## Dashboard and API Actions

You can perform the following actions:
- [Issue Normal refunds](https://razorpay.com/docs/build/llm-docs/payments/refunds/issue.md)
- [View Refunds](https://razorpay.com/docs/build/llm-docs/payments/refunds/view.md)
- [Handle refund errors](https://razorpay.com/docs/build/llm-docs/payments/refunds/errors.md)

### Related Information

- [Batch Refund](https://razorpay.com/docs/build/llm-docs/payments/refunds/batch.md)

- [Instant Refund](https://razorpay.com/docs/build/llm-docs/payments/refunds/instant.md)

- [Add funds to your account to process refunds (low account balance)](https://razorpay.com/docs/build/llm-docs/payments/dashboard/account-settings/balances.md#add-funds-to-your-current-balance)

- [Refunds API](https://razorpay.com/docs/build/llm-docs/payments/refunds/apis.md)

- [Subscribe to Webhooks](https://razorpay.com/docs/build/llm-docs/payments/refunds/subscribe-to-webhooks.md)

- [Refunds FAQs](https://razorpay.com/docs/build/llm-docs/payments/refunds/faqs.md)
