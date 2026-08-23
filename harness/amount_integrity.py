#!/usr/bin/env python
"""
P5 AMOUNT INTEGRITY -- turn a code-reading finding into an executed one.

Reading the source shows paymentAuthorized() computes the expected order amount and then never
compares it to the amount actually paid, while virtualAccountCredited() (same file, line 505) and
razorpay-edd (line 130) both do compare. That is a strong structural finding, but structural findings
are weaker evidence than behavioural ones, and this harness's whole thesis is that you execute rather
than reason.

So: create an order for one amount, deliver an authorized payment for a DIFFERENT amount, and read
the terminal state.

  order total  = Rs 499.00  (49900 paise)
  payment      = Rs 1.00    (  100 paise)

If the order still reaches a paid state, the invariant "amount paid == amount ordered" is not
enforced on this path, and that is now an observed fact rather than an inference.

HONEST SCOPE, to be stated wherever this result appears:
  * This is a MISSING INVARIANT, not a demonstrated attack. In production the signature is verified
    and the payment entity is fetched from Razorpay, so a real attacker does not simply get to pick
    the amount. What this shows is that the plugin does not defend the invariant itself.
  * The mismatched amount is supplied by our local stub, i.e. we are testing what the plugin does
    with a Razorpay-shaped response that disagrees with the order -- which is exactly the situation a
    missing check is supposed to catch.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rig  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UNDERPAY_PAISE = 100  # Rs 1.00 against an order of Rs 499.00


def main():
    print("=" * 92)
    print("P5 AMOUNT INTEGRITY -- does an underpaid authorization still complete the order?")
    print("=" * 92)

    wc, rzp, paise = rig.new_order()
    print("order %d  total = %d paise (Rs %.2f)" % (wc, paise, paise / 100.0))
    print("delivering an authorized payment for %d paise (Rs %.2f) -- a %d paise shortfall"
          % (UNDERPAY_PAISE, UNDERPAY_PAISE / 100.0, paise - UNDERPAY_PAISE))

    # pay_UNDER... makes the stub answer with the mismatched amount (see stub/router.php).
    path, sig = rig.build_event("payment.authorized", wc, rzp, UNDERPAY_PAISE,
                                payment_id="pay_UNDER%010d" % wc)
    code = subprocess.run(
        ["curl", "-s", "-o", os.devnull, "-w", "%{http_code}", "-X", "POST", rig.ENDPOINT,
         "-H", "Content-Type: application/json", "-H", "X-Razorpay-Signature: " + sig,
         "--data-binary", "@" + path],
        capture_output=True, text=True, timeout=120).stdout.strip()
    print("  HTTP %s" % code)

    rig.drain(wc)
    st = rig.terminal_state(wc)
    print("  terminal: %s" % json.dumps(st))

    paid = st["order_status"] in ("wc-processing", "wc-completed")
    print()
    print("=" * 92)
    if paid:
        print("RED -- the order reached %s having been paid %d paise against a %d paise total."
              % (st["order_status"], UNDERPAY_PAISE, paise))
        print("      The invariant 'amount paid == amount ordered' is not enforced on this path.")
        print("      Same file enforces it at razorpay-webhook.php:505 (virtual account);")
        print("      razorpay-edd enforces it at line 130. Two sibling paths check it; this one does not.")
    else:
        print("GREEN -- the order did not complete (%s). The invariant is enforced somewhere on this")
        print("        path after all, and the structural reading was incomplete." % st["order_status"])
    print("=" * 92)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rig", "out",
                       "amount_integrity.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"order": wc, "order_paise": paise, "paid_paise": UNDERPAY_PAISE,
                   "http": code, "terminal": st, "verdict": "RED" if paid else "GREEN"}, fh, indent=2)
    print("saved -> %s" % os.path.normpath(out))
    return 1 if paid else 0


if __name__ == "__main__":
    sys.exit(main())
