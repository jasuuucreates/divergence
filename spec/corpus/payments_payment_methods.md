---
title: About Payment Methods
description: Check the different payment methods that can be configured to accept payments from your customers using Razorpay products.
---

# About Payment Methods

The Razorpay Checkout offers multiple payment methods, allowing your customer the flexibility to complete the payment using the payment method of their choice. This improves user experience and allows you to offer alternate payment methods to your customer in the case of downtimes or low success rate with one of the payment methods. 

For example, if you are facing downtime with netbanking, the customer can complete the payment using cards or wallets.

You can view the payment methods enabled for your account or [raise requests for additional payment methods or providers](https://razorpay.com/docs/build/llm-docs/payments/dashboard/account-settings/payment-methods.md#enable-payment-methods) on the Dashboard. 

## View Payment Methods

To view payment methods enabled for you:
1. Log in to the Dashboard.
2. Click **Account & Settings** in the left menu.
    
3. Go to **Payment methods** to view the payment methods enabled for your Razorpay account.
    

You can also request for [Additional Payment Methods](https://razorpay.com/docs/build/llm-docs/payments/dashboard/account-settings/payment-methods.md#request-for-payment-methods) from the Dashboard.

## Supported Payment Methods

Following are all the payment modes that the customer can use to complete the payment on the Checkout. Some of them are available by default, while others require approval from us. Raise a request from the Dashboard to enable such payment methods.

Payment Method | Code | Availability
---
[Cash on Delivery](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/cod.md)  | `cod` | Requires [Approval](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/cod.md) and Integration.
---
Debit Card | `debit` | ✓
---
Credit Card | `credit` | ✓
---
[Netbanking](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/netbanking.md) | `netbanking`| ✓
---
[UPI](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/upi.md) | `upi` | ✓
---
EMI - [Credit Card EMI](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/emi/credit-card-emi.md), [Debit Card EMI](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/emi/debit-card-emi.md) and [No Cost EMI](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/emi/no-cost-emi.md) | `emi` | ✓
---
[Wallet](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/wallets.md#supported-wallets) | `wallet` | ✓
---
[Cardless EMI](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/emi/cardless-emi.md) | `cardless_emi` | Requires [Approval](https://razorpay.com/support).
---
[Bank Transfer](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/bank-transfer.md) | `bank_transfer` | Requires [Approval](https://razorpay.com/support) and Integration.
---
[Emandate](https://razorpay.com/docs/build/llm-docs/payments/recurring-payments/emandate/integrate.md) | `emandate` | Requires [Approval](https://razorpay.com/support) and Integration.
---
[Pay Later](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/pay-later.md)| `paylater` | Requires [Approval](https://razorpay.com/support).
---
[Sodexo](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/sodexo.md)| `TBD` | Requires [Approval](https://razorpay.com/support) if not on [Optimizer](https://razorpay.com/docs/build/llm-docs/payments/optimizer.md).

## Supported UPI apps

You can accept payments from customers through UPI apps, such as Google Pay, BHIM UPI and PhonePe. Razorpay supports multiple [third-party UPI apps](https://www.npci.org.in/what-we-do/upi/3rd-party-apps) and has direct integration with Google Pay.

You can select the appropriate method of [UPI integration](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/upi.md) based on the kind of checkout experience you want to give your customers.

## Google Pay Integration

In addition to the [standard](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/upi/google-pay.md) and [custom](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/upi/google-pay/custom-integration.md) checkout integrations, there are certain intent-based payment flows that you can enable on your Checkout. Know more about [Omnichannel](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/upi/google-pay/omnichannel.md) and [Google Pay SDK](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/upi/google-pay/custom-integration.md#intent-based-integration) integrations.

## Transaction Limits

- [Transaction Limits for Payment Methods](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/transaction-limits.md)
- [UPI Transaction Limits](https://razorpay.com/docs/build/llm-docs/payments/payment-methods/transaction-limits/upi.md)

## Payment Method Error Codes

There are certain error codes specific for each payment method supported by Razorpay. Know more about the [Payment Method Error Codes](https://razorpay.com/docs/build/llm-docs/errors/payments/payment-methods-error-parameters.md).
