# Where the documentation and the code disagree

*Verified 2026-08-24 against `master`. Every quotation below was fetched from the live file and
every counter-claim was produced by executing the plugin.*

In April 2026 Razorpay merged [PR #649](https://github.com/razorpay/razorpay-woocommerce/pull/649)
into `razorpay-woocommerce` — *"feat: Agentify repo with AI context, diagrams & multi-LLM support"*,
opened by their own agent bot. It added `docs/flows/webhook-flow.md`, a model-written description of
the webhook path derived from reading the source.

Two of its claims do not survive execution.

**Read this part first, because it is the part people skip:** the guards that document describes are
**real, and they work**. They genuinely prevent the duplicate-processing they were written to
prevent. Nothing below says the code is careless or the documentation is dishonest. What it says is
narrower and, I think, more interesting: *a model reading source code concluded a property held, and
nobody ran a test that could have contradicted it.*

---

## 1. "Idempotent order processing"

> *"Razorpay webhooks provide server-to-server notifications for payment events. The plugin processes
> them asynchronously to prevent timeout issues and **ensure idempotent order processing**."*
> — `docs/flows/webhook-flow.md`, line 5

The document's **Idempotency Handling** table lists four checks:

| Check | Where |
|---|---|
| `order->needs_payment()` | `paymentAuthorized()` |
| `rzp_update_order_cron_status = 1` | Cron job |
| `refund_from_website = true` | `refundedCreated()` |
| `invoice_id` check | Multiple handlers |

**All four are single-event state guards.** Each asks "has this already happened?" None constrains
the *order* in which events arrive. The 197-line document contains no treatment of out-of-order or
concurrent delivery anywhere — the only matches for "sequence" are a section heading and the word
`sequenceDiagram`.

**What execution shows.** The same two events, delivered in the two orders Razorpay's *own webhook
documentation* says are both legal, reach different terminal states:

```
payment.authorized  then  refund.created   ->  wc-refunded
refund.created  then  payment.authorized   ->  wc-processing
```

`wc-processing` means paid, fulfil the order. The refund was silently discarded — and the trace shows
it was not deferred or recorded elsewhere: across all 193 database statements that delivery issued,
there is no refund at all (`harness/trace.py --compare`).

Idempotency and order-independence are different properties. The document's guards deliver the first
and are silent about the second, but the sentence at line 5 reads as a guarantee about processing in
general.

---

## 2. "JSON array with new event"

> *`WH->>DB: SELECT rzp_webhook_data FROM rzp_webhook_requests WHERE order_id AND rzp_order_id`*
> *`WH->>DB: UPDATE rzp_webhook_data = JSON array with new event, notified_at = now()`*
> — same file, lines 80–81

That describes read-then-append: fetch the stored events, add the new one, write it back. The schema
in the same document supports that reading — `rzp_webhook_data LONGTEXT DEFAULT '[]'`.

**What execution shows.** It never appends. `saveWebhookEvent()` reads with `$wpdb->get_results()`,
which returns a numerically-indexed array of row objects, and then subscripts it with the *string*
`'rzp_webhook_data'`. That key does not exist, so the read yields `null`, `(array) null` is `[]`, and
the "new event" is written into an empty list every time.

Three distinct authorized payments on one order:

```
pay_...0001 arrives  ->  stored: [0001]
pay_...0002 arrives  ->  stored: [0002]     0001 is gone
pay_...0003 arrives  ->  stored: [0003]     0002 is gone
```

The plugin logs its own warning while doing it: `PHP Warning: Undefined array key "rzp_webhook_data"`.

The intent is visible on both sides of the code — the write does `$rzpWebhookData[] = $data`, and the
cron reads it back with `foreach ($events as $event)`. Both were written expecting a list. One type
error defeats both, and the documentation describes the intent rather than the behaviour.

---

## Why this belongs in this repository

Not as an embarrassment. As the clearest available statement of what this harness is for.

A model read the source and concluded the webhook path was idempotent. That conclusion is what
careful source-reading produces, and it is wrong in a way that only running the code reveals. **Both
this project and that document used AI. The difference is where.** Here the model's job stops at
proposing what to check; the verdict is a deterministic comparison against executed state, and
`harness/gate.py` will reject a proposed property that no variant of the integration can violate.

That is the whole argument, and Razorpay's own repository is the example.

## Reproduce

```bash
curl -s https://raw.githubusercontent.com/razorpay/razorpay-woocommerce/master/docs/flows/webhook-flow.md | sed -n '5p;80,81p'
cd rig && ./setup.sh
python harness/check.py            # P1 RED
python harness/trace.py --compare  # 0 refund rows in the losing ordering
```
