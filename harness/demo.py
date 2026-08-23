#!/usr/bin/env python
"""
The live demonstration.

A recorded video and a live demo are different problems. A video can be re-shot; a live demo happens
once, in front of people, on a laptop that was fine an hour ago. So this is built around three rules:

  1. NOTHING IS SHOWN UNTIL EVERYTHING IS CHECKED. `--preflight` verifies the whole chain before the
     audience sees anything. Run it while walking to the room.
  2. THE FIRST INTERESTING THING HAPPENS IN UNDER A MINUTE. Nobody watches a progress bar.
  3. A FAILURE MID-DEMO IS NARRATED, NOT HIDDEN. If a step cannot run, it says what broke and what
     that means, and carries on. A harness whose whole argument is "refuse to report what you did
     not measure" cannot quietly skip a broken step on stage.

    python harness/demo.py --preflight     # BEFORE the demo. ~30s. Fix anything red.
    python harness/demo.py                 # the demo itself, ~2 minutes
    python harness/demo.py --deep contract # answer a specific question with evidence
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RIG = os.path.join(ROOT, "rig")

sys.path.insert(0, HERE)
import contract   # noqa: E402
import dockerenv  # noqa: E402
import measured   # noqa: E402
import rig        # noqa: E402
import runlock    # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

W = 78


def rule(ch="="):
    print(ch * W)


def head(t):
    print()
    rule()
    print("  " + t)
    rule()


def beat(seconds=1.2):
    """Deliberate pacing. Output that scrolls faster than someone can speak is output nobody reads."""
    sys.stdout.flush()
    time.sleep(seconds)


# ---------------------------------------------------------------------------------------------
# PREFLIGHT -- run this before standing up, not during
# ---------------------------------------------------------------------------------------------
def preflight():
    head("PREFLIGHT -- run this BEFORE the demo, not during it")
    checks, ok = [], True

    def check(name, fn):
        nonlocal ok
        try:
            detail = fn()
            print("  PASS  %-34s %s" % (name, detail or ""))
            checks.append({"check": name, "pass": True, "detail": detail})
        except Exception as e:
            ok = False
            print("  FAIL  %-34s %s" % (name, str(e).splitlines()[0][:40]))
            checks.append({"check": name, "pass": False, "detail": str(e)[:300]})

    check("docker engine", lambda: dockerenv.require())

    def containers():
        p = subprocess.run(["docker", "compose", "ps", "--format", "{{.Service}} {{.State}}"],
                           cwd=RIG, env=dockerenv.shell(), capture_output=True, text=True, timeout=90)
        svc = dict(l.split()[:2] for l in (p.stdout or "").splitlines() if len(l.split()) >= 2)
        missing = [s for s in ("db", "wordpress", "rzpstub") if svc.get(s) != "running"]
        if missing:
            raise RuntimeError("not running: %s -- cd rig && ./setup.sh" % ", ".join(missing))
        return "db, wordpress, rzpstub all running"
    check("containers", containers)

    def stub():
        p = subprocess.run(["docker", "compose", "exec", "-T", "wordpress", "sh", "-c",
                            "curl -s -o /dev/null -w '%{http_code}' "
                            "http://rzpstub:8000/v1/payments/pay_RIG00000000001"],
                           cwd=RIG, env=dockerenv.shell(), capture_output=True, text=True, timeout=90)
        if (p.stdout or "").strip() != "200":
            raise RuntimeError("stub not answering -- every verdict would be meaningless")
        return "answering 200"
    check("api stub", stub)

    def plugins():
        got = rig.wp("plugin", "list", "--status=active", "--field=name")
        names = {l.strip() for l in got.splitlines() if l.strip() and not l.startswith(("Warning", "["))}
        need = {"woocommerce", "razorpay-woocommerce"}
        if not need <= names:
            raise RuntimeError("missing %s -- run harness/matrix.py to activate" % (need - names))
        return ", ".join(sorted(need))
    check("gateway plugins active", plugins)

    def speed():
        t = time.time()
        wc, rzp, paise = rig.new_order()
        dt = time.time() - t
        if dt > 6:
            raise RuntimeError("order creation took %.1fs -- the fast wp-cli path is not active" % dt)
        return "order created in %.1fs (fast path %s)" % (dt, "on" if rig._WP_FAST else "OFF")
    check("speed (fast wp-cli path)", speed)

    def unmodified():
        p = subprocess.run(["git", "status", "--porcelain"],
                           cwd=os.path.join(RIG, "plugin", "razorpay-woocommerce"),
                           capture_output=True, text=True, timeout=90)
        if (p.stdout or "").strip():
            raise RuntimeError("the plugin under test is MODIFIED -- restore it before demoing")
        d = subprocess.run(["git", "describe", "--tags", "--always"],
                           cwd=os.path.join(RIG, "plugin", "razorpay-woocommerce"),
                           capture_output=True, text=True, timeout=90)
        return "clean at %s" % (d.stdout or "?").strip()
    check("plugin under test unmodified", unmodified)

    print()
    rule()
    print("  %s" % ("READY." if ok else "NOT READY -- fix the FAILs above before demoing."))
    rule()
    io.open(os.path.join(RIG, "out", "preflight.json"), "w", encoding="utf-8").write(
        json.dumps({"ok": ok, "checks": checks}, indent=2))
    return 0 if ok else 1


# ---------------------------------------------------------------------------------------------
# THE DEMO
# ---------------------------------------------------------------------------------------------
def demo():
    head("DIVERGENCE -- a conformance harness for payment integrations")
    print("  Target : razorpay/razorpay-woocommerce v4.8.7, unmodified, 100,000+ installs")
    print("  Method : run the real plugin; check it against its vendor's own documentation")
    beat()

    print("\n  Razorpay's documentation says this, verbatim:\n")
    print("      \"%s\"" % contract.ORDER_INDEPENDENCE.doc_quote)
    print("\n  That sentence is a specification. Here it is as a test.")
    beat(2.0)

    head("SAME TWO EVENTS. SAME SIGNATURES. ONLY THE ORDER DIFFERS.")
    results = {}
    for label, seq in (("authorization settles first", ["payment.authorized", "refund.created"]),
                       ("refund arrives first", ["refund.created", "payment.authorized"])):
        print("\n  %s" % label)
        print("    %s" % "  ->  ".join(seq))
        sys.stdout.flush()
        t = rig.trial(list(seq))
        try:
            measured.require([t], "order_status")
        except measured.NotMeasured as e:
            print("    COULD NOT MEASURE: %s" % str(e).splitlines()[0])
            print("    Not reporting a verdict for this arm. See INCIDENTS.md for why that matters.")
            return 1
        st = t["terminal"]["order_status"]
        results[label] = st
        print("    order #%s ends:  %s" % (t["order"], st.upper()))
        beat(1.5)

    a, b = results.values()
    print()
    rule()
    if a != b:
        print("  The same two events, delivered in the two orders the vendor says are both legal,")
        print("  leave the shop in two different states.")
        print()
        print("    wc-refunded    the customer got their money back")
        print("    wc-processing  PAID. Fulfil this order.")
        print()
        print("  In the second one the refund was silently discarded, and the shop is about to")
        print("  ship goods for an order that has already been refunded.")
    else:
        print("  Both orderings converged on %s. No divergence in this run." % a)
        print("  That is a real result, not a failed demo -- and it would mean the plugin changed.")
    rule()
    beat(2.5)

    head("WHY THIS IS NOT A RACE YOU COULD GET LUCKY WITH")
    print("  payment.authorized is parked for a cron that only picks up rows older than 300s.")
    print("  Refunds are handled the moment they arrive.")
    print()
    print("      woo-razorpay.php:3393   rzp_webhook_notified_at < time()-300")
    print()
    print("  So any refund inside that five-minute window takes the losing path. Every time.")
    beat(2.0)

    head("AND IT IS NOT A SCRIPT THAT PRINTS MY OWN BUGS")
    print("  The same harness, the same property, against Razorpay's OTHER plugin:")
    print()
    print("      razorpay-woocommerce   Rs 499 order, Rs 1 paid  ->  RED    completes the order")
    print("      razorpay-edd           Rs 499 order, Rs 1 paid  ->  GREEN  refuses it")
    print()
    print("  A harness that says RED everywhere is a bug list. The GREEN is the point.")
    print("  (Run harness/matrix.py to see both live -- about 50 seconds.)")
    beat(2.0)

    head("WHAT I GOT WRONG")
    print("  INCIDENTS.md -- 14 dated entries, every time this project produced a wrong result.")
    print()
    print("    - a headline percentage that was an artefact of how I sampled")
    print("    - a citation I wrote myself and presented as a quotation from Razorpay")
    print("    - the harness reporting GREEN having measured nothing, four separate times")
    print("    - a false PASS from a plugin that was not running at all")
    print()
    print("  The last two are why every property now refuses to answer without evidence.")
    rule()
    print("  Everything here is reproducible: cd rig && ./setup.sh, then harness/check.py")
    rule()
    return 0


def deep(topic):
    """Answer a specific question with evidence, mid-demo, without leaving the terminal."""
    if topic == "contract":
        head("THE CONTRACT -- every property cites the sentence that makes it normative")
        for c in contract.citations():
            print("\n  %-24s [%s]" % (c["key"], c["kind"].upper()))
            print("    %s" % c["title"])
            print("    vendor: \"%s\"" % c["vendor_says"][:150])
            print("    source: %s" % c["source"])
    elif topic == "evidence":
        head("EVIDENCE -- every number has a transcript")
        for fn in sorted(os.listdir(os.path.join(ROOT, "evidence"))):
            p = os.path.join(ROOT, "evidence", fn)
            if os.path.isfile(p):
                print("  %-34s %8d B" % (fn, os.path.getsize(p)))
    elif topic == "limits":
        head("LIMITATIONS -- read before the results")
        txt = io.open(os.path.join(ROOT, "LIMITATIONS.md"), encoding="utf-8").read()
        for line in txt.splitlines()[:44]:
            print("  " + line)
    else:
        print("topics: contract | evidence | limits")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--deep", help="contract | evidence | limits")
    a = ap.parse_args()
    if a.preflight:
        sys.exit(preflight())
    if a.deep:
        sys.exit(deep(a.deep))
    try:
        with runlock.exclusive("demo"):
            sys.exit(demo())
    except runlock.RigBusy as e:
        print("REFUSING TO START.")
        print(e)
        sys.exit(2)
