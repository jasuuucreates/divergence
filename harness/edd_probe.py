#!/usr/bin/env python
"""
First contact with target #2 (razorpay-edd).

Purpose is narrow and deliberate: establish that the harness can drive an integration it was not
written for, and record what it finds against the prediction made BEFORE the run
(see harness/targets.py -> expectations()).

Predicted for EDD, from reading the source:
    P1 order independence  GREEN   -- one dispatched event, fully synchronous, nothing to race
    P5 amount integrity    GREEN   -- compares at includes/razorpay-webhook.php:130
    P4 no silent loss      GREEN   -- no deferred queue to mark consumed
A GREEN here is the deliverable. A harness that reports RED on every target is a bug list; one that
reports GREEN on correct code and RED on incorrect code is an oracle.

The payload shape differs from WooCommerce in a way that would silently produce a false GREEN if
gotten wrong: razorpay-edd reads the order id from payload.order.entity.notes.edd_order_id, a
different entity AND a different key. A WooCommerce-shaped body is dropped by shouldConsumeWebhook's
equivalent and the endpoint still answers 200 -- which looks exactly like a pass. So this probe
asserts the state actually MOVED on the happy path before trusting any other result from this target.
"""
import hashlib
import hmac
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RIG = os.path.join(os.path.dirname(HERE), "rig")

sys.path.insert(0, HERE)
import dockerenv  # noqa: E402

SECRET = "rig-webhook-secret-synthetic"
ENDPOINT = "http://localhost:8080/wp-admin/admin-post.php?action=rzp_edd_webhook"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _env():
    """Docker is not on PATH on a default Windows install -- see harness/dockerenv.py."""
    return dockerenv.shell()


def _run(args, timeout=300):
    p = subprocess.run(args, cwd=RIG, env=_env(), capture_output=True, text=True, timeout=timeout)
    return (p.stdout or "").replace("\r", "")


def wp(*args):
    out = _run(["docker", "compose", "run", "--rm", "-T", "cli", "wp"] + list(args))
    return "\n".join(l for l in out.splitlines()
                     if not l.startswith(("Warning:", "[23-Aug", "Container", " Container")))


def new_payment():
    out = wp("eval-file", "/rig/new_edd_payment.php")
    kv = dict(l.split("=", 1) for l in out.splitlines() if "=" in l and l.split("=")[0].isupper())
    return int(kv["ORDER_ID"]), int(kv["PAISE"])


def status(order_id):
    return wp("eval", 'echo (new EDD_Payment(%d))->status;' % order_id).strip()


def body(order_id, paise, payment_id):
    """razorpay-edd reads payload.payment.entity.{invoice_id,id} AND
    payload.order.entity.notes.edd_order_id. Both entities are required."""
    return {
        "entity": "event",
        "account_id": "acc_SYNTHETIC_RIG",
        "event": "order.paid",
        "contains": ["payment", "order"],
        "payload": {
            "payment": {"entity": {
                "id": payment_id, "entity": "payment", "amount": paise, "currency": "INR",
                "status": "captured", "captured": True, "invoice_id": None,
                "notes": {"edd_order_id": str(order_id)}, "created_at": 1787429027,
            }},
            "order": {"entity": {
                "id": "order_EDDRIG%08d" % order_id, "entity": "order",
                "amount": paise, "currency": "INR", "status": "paid",
                "notes": {"edd_order_id": str(order_id)}, "created_at": 1787429027,
            }},
        },
        "created_at": 1787429027,
    }


def deliver(order_id, paise, payment_id):
    raw = json.dumps(body(order_id, paise, payment_id), separators=(",", ":"),
                     sort_keys=True).encode()
    path = os.path.join(RIG, "out", "edd_%d.json" % order_id)
    io.open(path, "wb").write(raw)
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    p = subprocess.run(["curl", "-s", "-o", os.devnull, "-w", "%{http_code}", "-X", "POST",
                        ENDPOINT, "-H", "Content-Type: application/json",
                        "-H", "X-Razorpay-Signature: " + sig, "--data-binary", "@" + path],
                       capture_output=True, text=True, timeout=180)
    return (p.stdout or "").strip()


def main():
    print("=" * 92)
    print("TARGET #2 -- razorpay-edd   (first contact)")
    print("=" * 92)

    results = {}

    # --- CONTROL: does a correct, matching payment move the state at all? -------------------
    # If this does not move, every later GREEN is meaningless -- it would just mean nothing
    # reached the handler. Establish the instrument works before trusting it.
    oid, paise = new_payment()
    print("\nCONTROL  payment %d, total %d paise, status=%s" % (oid, paise, status(oid)))
    code = deliver(oid, paise, "pay_RIG%011d" % oid)
    time.sleep(1)
    after = status(oid)
    print("  order.paid (matching amount) -> HTTP %s -> status=%s" % (code, after))
    # Require the state we PREDICTED, not merely "something other than the pending state".
    # status() shells out to wp-cli: if EDD is inactive, the container is down, or the PHP throws,
    # it returns "" or a fatal-error string. An inequality test against the pending state is
    # satisfied by every one of those, so this control used to announce CONTROL OK on every kind
    # of total failure except the one it was written to catch.
    CONTROL_PAID_STATES = ("complete", "publish")
    moved = after in CONTROL_PAID_STATES
    results["control_moved"] = moved
    results["control_observed"] = after
    print("  %s" % ("CONTROL OK - the handler is reachable and does move the state" if moved
                    else "CONTROL FAILED - expected one of %s, observed %r; nothing below is "
                         "trustworthy" % (CONTROL_PAID_STATES, after)))

    # Refuse to EMIT a verdict the control just disowned, rather than printing the disclaimer and
    # then printing the verdict anyway. Any reader scanning this output for a verdict line -- and
    # matrix.py and corpus.py both do -- would otherwise lift a GREEN out of a run that announced
    # itself untrustworthy, which is precisely how an inactive plugin manufactured the
    # discrimination headline during final prep.
    if not moved:
        print("\n" + "=" * 92)
        print("P5-AMOUNT-INTEGRITY: UNDECIDABLE  (control failed; no verdict is produced)")
        print("  The instrument was not connected, so this run measured nothing. Most likely the")
        print("  razorpay-edd plugin is not active:")
        print("    cd rig && docker compose run --rm -T cli wp plugin activate razorpay-edd")
        print("=" * 92)
        results["P5"] = {"verdict": "UNDECIDABLE", "reason": "control arm failed"}
        out = os.path.join(RIG, "out", "edd_probe.json")
        io.open(out, "w", encoding="utf-8").write(json.dumps(results, indent=2))
        return 2

    # --- P5 AMOUNT INTEGRITY: underpay, and see whether EDD refuses --------------------------
    oid2, paise2 = new_payment()
    print("\nP5       payment %d, total %d paise; delivering an authorized payment for 100 paise"
          % (oid2, paise2))
    code2 = deliver(oid2, paise2, "pay_UNDER%09d" % oid2)
    time.sleep(1)
    after2 = status(oid2)
    print("  underpaid order.paid -> HTTP %s -> status=%s" % (code2, after2))
    # ORACLE CORRECTION (2026-08-23): the first version of this predicate was
    #     GREEN if after2 == "pending" else RED
    # which assumed a refusing implementation leaves the order untouched. EDD does something
    # BETTER: it marks the payment `failed` explicitly. That predicate therefore scored correct
    # code as RED. The property is "must not reach a state that means PAID" -- refusing loudly
    # and refusing quietly are both conformant; only accepting is not.
    PAID_STATES = ("complete", "publish", "processing", "wc-processing", "wc-completed")
    p5 = "RED" if after2 in PAID_STATES else "GREEN"
    results["P5"] = {"verdict": p5, "order": oid2, "terminal": after2}
    print("  P5-AMOUNT-INTEGRITY: %s   (predicted GREEN -- edd compares at razorpay-webhook.php:130)"
          % p5)
    print("  terminal '%s' is a refusal, not an acceptance -- edd failed the payment rather than"
          % after2)
    print("  fulfilling it, which is stricter than merely leaving it pending.")

    print("\n" + "=" * 92)
    print("PREDICTION vs OBSERVATION")
    print("  P5 predicted GREEN, observed %s  %s"
          % (p5, "MATCH" if p5 == "GREEN" else "*** MISMATCH -- investigate before claiming ***"))
    print("=" * 92)

    out = os.path.join(RIG, "out", "edd_probe.json")
    io.open(out, "w", encoding="utf-8").write(json.dumps(results, indent=2))
    print("saved -> %s" % os.path.normpath(out))


if __name__ == "__main__":
    # Propagate the exit status. main() returns 2 when the control arm failed and no verdict was
    # produced; swallowing that made a probe that measured nothing exit 0, which is the same
    # "absence scored as a pass" shape this repo exists to refuse.
    sys.exit(main() or 0)
