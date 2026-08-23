---
title: Handle Refund Errors
description: Check the errors that may occur while processing Refunds and how to handle these errors.
---

# Handle Refund Errors

Sometimes when you try to process a refund request, it fails to get processed and you may encounter `BAD_REQUEST_ERROR` messages stating refunds are not supported. This happens because most of the banks do not support refunds for payments that are more than 6 months old.

## List of Possible Refund Errors

Given below is a refund error example.

```json: Error Response 
{
  "error": {
    "code": "BAD_REQUEST_ERROR",
    "description": "Refund is not supported by the bank because the payment is more than 6 months old",
    "source": null,
    "step": null,
    "reason": null,
    "metadata": {}
  }
}
```

You can try to process such refunds using [**Instant Refund**](https://razorpay.com/docs/build/llm-docs/payments/refunds/instant.md). To check the refund status, navigate to the **Refund Details** pop-up by clicking on the specific **Refund Id** under the **Transactions** → **Refunds** tab.

You can get the ARN/RRN for successfully processed refunds under the [Dashboard Refunds tab](https://razorpay.com/docs/build/llm-docs/payments/refunds/view.md) or using the [Fetch Refund API](https://razorpay.com/docs/build/llm-docs/api/refunds.md#fetch-refund-by-id). This is a unique reference number which can be used by the customers to track refunds.

**INFO**

**Instant Refund Fee**

We charge a [small fee to process instant refunds](https://razorpay.com/docs/build/llm-docs/payments/refunds/instant.md#refund-fees).

If **Instant Refund** for a payment that is more than 6 months old is not supported, an error message is displayed on the **Refund Payment** pop-up.

You will encounter the following error code and error message in the API response:

```json: Error Response
{
  "error": {
    "code": "BAD_REQUEST_ERROR",
    "description": "Refund is not supported by the bank because the payment is more than 6 months old",
    "source": null,
    "step": null,
    "reason": null,
    "metadata": {}
  }
}
```

**INFO**

**Instant Refund Fee Reversal**

If the instant refund fails, any fee charged will be reversed to your account.

### Related Information

- [About Refunds](https://razorpay.com/docs/build/llm-docs/payments/refunds.md)

- [Normal Refunds](https://razorpay.com/docs/build/llm-docs/payments/refunds/normal.md)

- [Instant Refunds](https://razorpay.com/docs/build/llm-docs/payments/refunds/instant.md)

- [Batch Refund](https://razorpay.com/docs/build/llm-docs/payments/refunds/batch.md)

- [Refunds FAQs](https://razorpay.com/docs/build/llm-docs/payments/refunds/faqs.md)
