---
title: Issue Refunds
description: Issue refunds to customers using Razorpay Dashboard and APIs.
---

# Issue Refunds

You can issue refunds to your customers using the Dashboard or APIs. Refunds are possible for `captured` payments only.

**INFO**

**Customer Looking for Refund**

If you are a customer looking for a refund, know about [customer refunds](https://razorpay.com/docs/build/llm-docs/payments/customers/customer-refunds.md).

## Full and Partial Refunds

Refunds can be made either in **full** or in **part**.

- **Full Refund**

You can refund the entire amount that you received in the payment.

- **Partial Refund**

You can refund part of the amount received in the payment. You can issue multiple, partial refunds as long as their sum does not exceed the captured amount.

A payment moves to the `refunded` state only when the entire amount is refunded to the customer. In case of partial refunds, the payment remains in the `captured` state till the entire payment is refunded.

## Issue Refunds

### Issue Refunds Using Dashboard

Watch this video to see how to issue a refund.

To issue refunds:

1. Log in to the Dashboard.
2. Navigate to **Transactions** → **Payments**.
3. Select the payment for which refund is requested. The payment should be in the `captured` state.
4. On the **Refund Payment** page, in the **amount** field, enter an amount lesser than the captured amount for issuing a partial refund.
By default, the entire amount will be refunded.
5. Look for the **Refund Instantly** check box.
    - If you want to issue a normal refund, unselect the **Refund Instantly** check box.
     
    - If you want to issue an [instant refund](https://razorpay.com/docs/build/llm-docs/payments/refunds/instant.md), select the **Refund Instantly** check box.
    
6. Review the fees that will be levied for the refund to be processed instantly. 
7. Click the **Issue Full Refund** or **Issue Partial Refund** button, depending on the amount to be refunded.

### Issue Refunds Using API

To create a normal refund, use [Create a Normal Refund API](https://razorpay.com/docs/build/llm-docs/api/refunds/create-normal.md).

### Related Information

- [About Refunds](https://razorpay.com/docs/build/llm-docs/payments/refunds.md)

- [Normal Refunds](https://razorpay.com/docs/build/llm-docs/payments/refunds/normal.md)

- [Instant Refunds](https://razorpay.com/docs/build/llm-docs/payments/refunds/instant.md)

- [Batch Refunds](https://razorpay.com/docs/build/llm-docs/payments/refunds/batch.md)

- [View Refunds](https://razorpay.com/docs/build/llm-docs/payments/refunds/view.md)

- [Refunds FAQs](https://razorpay.com/docs/build/llm-docs/payments/refunds/faqs.md)
