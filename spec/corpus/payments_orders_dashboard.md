---
title: Orders - Dashboard Actions
description: View Order details, subscribe to webhook events and view reports from the Razorpay Dashboard.
---

# Orders - Dashboard Actions

You can use the Dashboard to perform the following actions:
- [View Order Details from Dashboard](#view-order-details-from-dashboard)
- [Subscribe to Webhooks](#subscribe-to-webhook-events)
- [View reports](#reports)

## View Order Details From Dashboard

Watch this video to see how to view order details from the Dashboard.

To view order details:
1. Log in to the Dashboard.
2. Select **Transactions** from the left menu and click **View All** on the **Orders** tab.
3. A list of all the orders is displayed.
4. Click an **Order Id** to view the details of the order.

### View Order Details Using API

- [View all orders using Fetch Orders API](https://razorpay.com/docs/build/llm-docs/api/orders/fetch-all.md).
- [View specific details of an order using Fetch an Order with ID API](https://razorpay.com/docs/build/llm-docs/api/orders/fetch-with-id.md).

## Subscribe to Webhook Events

Subscribe to Webhook events available for orders to receive notifications.

To subscribe to Webhook events:

1. Log in to the Dashboard.
2. Navigate to **Accounts & Settings** → Webhooks to subscribe to any of the following events:

The table below lists the webhook events available for orders.

Webhook Event | Description
---
`order.paid` | Triggered when an order is successfully paid.

Know more about [Webhooks](https://razorpay.com/docs/build/llm-docs/webhooks.md) and check the [sample payloads](https://razorpay.com/docs/build/llm-docs/webhooks/orders.md).

## Reports

Detailed insights can be gained using reports and real-time data on the Dashboard. These reports can then be used for accounting and reconciliation purposes. Know more about [reports](https://razorpay.com/docs/build/llm-docs/payments/dashboard/reports.md).

### Related Information
- [About Orders](https://razorpay.com/docs/build/llm-docs/payments/orders.md)
- [Orders APIs](https://razorpay.com/docs/build/llm-docs/payments/orders/apis.md)
