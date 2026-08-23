#!/usr/bin/env python3
"""Build a Razorpay webhook body and write it to --out as raw bytes.

Prints the output path. probe.sh signs THOSE EXACT BYTES, so what is hashed
and what is sent are guaranteed identical.

Two fields are load-bearing:
  payload.payment.entity.notes.woocommerce_order_id
      shouldConsumeWebhook() (includes/razorpay-webhook.php:575-584) DROPS any
      delivery lacking it, BEFORE any signature check.
  payload.payment.entity.invoice_id
      razorpay-webhook.php:155 reads this key unconditionally. Sending null
      keeps PHP 8 quiet and paymentAuthorized() treats null as "not an invoice".

Nothing person-shaped appears here: no contact number, no card value, no
government id. All values synthetic.
"""
import argparse, json, os, sys, time


def payment_entity(wc_order_id, rzp_order_id, payment_id, paise, status):
    return {
        "id": payment_id, "entity": "payment",
        "amount": paise, "currency": "INR", "status": status,
        "order_id": rzp_order_id, "invoice_id": None,
        "international": False, "method": "upi",
        "amount_refunded": 0, "captured": status == "captured",
        "description": "Rig synthetic payment",
        "notes": {"woocommerce_order_id": str(wc_order_id)},  # Razorpay sends notes as strings
        "fee": None, "tax": None,
        "error_code": None, "error_description": None,
        "created_at": int(time.time()),
    }


def build(event, wc_order_id, rzp_order_id, payment_id, paise, refund_id):
    status = {
        "payment.authorized": "authorized",
        "payment.failed":     "failed",
        "payment.pending":    "pending",
        "refund.created":     "captured",
    }.get(event, "captured")
    pay = payment_entity(wc_order_id, rzp_order_id, payment_id, paise, status)
    body = {
        "entity": "event", "account_id": "acc_SYNTHETIC_RIG",
        "event": event, "contains": ["payment"],
        "payload": {"payment": {"entity": pay}},
        "created_at": int(time.time()),
    }
    if event == "refund.created":
        # refundedCreated() (razorpay-webhook.php:606-...) reads
        # payload.refund.entity.{payment_id,id,amount,notes.comment}
        # unconditionally, and returns early if notes.refund_from_website is set.
        body["contains"] = ["payment", "refund"]
        body["payload"]["refund"] = {"entity": {
            "id": refund_id, "entity": "refund", "amount": paise,
            "currency": "INR", "payment_id": payment_id,
            "notes": {"comment": "rig synthetic refund"},
            "created_at": int(time.time()),
        }}
    return body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", default="payment.authorized",
                    choices=["payment.authorized", "payment.failed", "payment.pending", "refund.created"])
    ap.add_argument("--wc-order", required=True)
    ap.add_argument("--rzp-order", required=True)
    ap.add_argument("--payment-id", default="pay_RIGSYNTH0000001")
    ap.add_argument("--refund-id", default="rfnd_RIGSYNTH000001")
    ap.add_argument("--amount", type=int, default=49900, help="paise")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    body = build(a.event, a.wc_order, a.rzp_order, a.payment_id, a.amount, a.refund_id)
    # Compact + stable: the bytes signed must equal the bytes sent.
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    # Binary mode: never let Windows translate \n to \r\n. One injected CR
    # changes the body and every signature check fails.
    with open(a.out, "wb") as fh:
        fh.write(raw)
    print(a.out)


if __name__ == "__main__":
    main()
