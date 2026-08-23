---
title: API | Orders
heading: Orders
description: Create, view and update an Order using Razorpay APIs.
---

# Orders

You can create [Orders](https://razorpay.com/docs/build/llm-docs/payments/orders.md) and link them to payments. Orders APIs are used to create, update and retrieve details of Orders. Also, you can retrieve details of payments made towards these Orders.

Fork the Razorpay Postman Public Workspace and try the Orders APIs using your [Test API Keys](https://razorpay.com/docs/build/llm-docs/payments/dashboard/account-settings/api-keys.md#generate-api-keys).

[](https://www.postman.com/razorpaydev/workspace/razorpay-public-workspace/folder/12492020-91450029-1c52-4375-8033-39ca4c2d0a8c)

### Related Guides

[About Orders](https://razorpay.com/docs/build/llm-docs/payments/orders.md)
[Set Up Webhooks](https://razorpay.com/docs/build/llm-docs/webhooks/setup-edit-payments.md)
[Webhook Payloads](https://razorpay.com/docs/build/llm-docs/webhooks/orders.md)

### Endpoints

  - **post** `/v1/orders` - Create an Order: 
    Creates an order by providing basic details such as amount and currency.
  

  - **get** `/v1/orders` - Fetch All Orders: 
    Retrieves details of all the orders.
  

  - **get** `/v1/orders?expand[]=payments` - Fetch All Orders (Example 1): 
    Retrieves details of all the orders and expands the payments object.
  

  - **get** `/v1/orders?expand[]=payments.card` - Fetch All Orders (Example 2): 
    Retrieves details of all the orders and expands cards parameter in the payments object.
  

  - **get** `/v1/orders/:id` - Fetch Order With ID: 
    Retrieves details of a particular order.
  

  - **get** `/v1/orders/:id/payments` - Fetch All Payments for an Order: 
    Retrieves all the payments made for an order.
  

  - **patch** `/v1/orders/:id` - Update an Order: 
    Modifies an existing order.
