---
title: Auto Third-Party Validation (TPV) on Smart Collect
description: Perform auto third-party validation of bank accounts provided by your customers using Razorpay Smart Collect API.
---

# Auto Third-Party Validation (TPV) on Smart Collect

Third-party validation is a very important step in the Banking, Financial Services and Insurance sector. As per SEBI guidelines, businesses operating in these sectors must ensure that payments are accepted from the customers' registered, KYC-approved bank accounts only.

 

- Using Razorpay Smart Collect API, you can comply with the regulatory guidelines to ensure that the customers make payments only from their registered bank accounts (TPV). 
- If payments are made from the unregistered accounts (non-TPV), they are automatically refunded to the customers.
- When you create a Customer Identifier, send the `allowed_payers` array with the customer's bank `account_number` and `ifsc`. This helps to identify TPV transactions and automatically refund non-TPV transactions.

Know more about [API Endpoints](https://razorpay.com/docs/build/llm-docs/api/payments/smart-collect-tpv.md) and [the list of banks that support TPV](https://razorpay.com/docs/build/llm-docs/payments/third-party-validation/bank-list.md).

### Related Information
- [Razorpay Smart Collect](https://razorpay.com/docs/build/llm-docs/payments/smart-collect.md)
- [How Smart Collect Works](https://razorpay.com/docs/build/llm-docs/payments/smart-collect/how-it-works.md)
- [Customer Identifier States](https://razorpay.com/docs/build/llm-docs/payments/smart-collect/states.md)
- [Refund Failures](https://razorpay.com/docs/build/llm-docs/payments/smart-collect/refund-failures.md)
- [Smart Collect APIs](https://razorpay.com/docs/build/llm-docs/api/payments/smart-collect.md)
- [Subscribe to Webhooks](https://razorpay.com/docs/build/llm-docs/payments/smart-collect/subscribe-to-webhooks.md)
