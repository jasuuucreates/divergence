#!/usr/bin/env python
"""
Making the documentation executable -- stage 4: is each property actually falsifiable?

A property that no code can violate is not a test. It reports GREEN forever, it makes the
specification look larger, and it measures nothing. If a specification is going to be assembled
partly from model proposals, this is the check that stops it being padded.

So: run the full property suite against several variants of the integration, and record for each
property whether ANY variant made it fail. A property never once RED across the whole corpus is
reported as VACUOUS -- not as passing.

This is mutation testing's central idea, pointed at the specification instead of at the test suite.
In mutation testing you ask "would my tests notice if the code changed?"; here we ask "would this
property notice if the integration were wrong?"

The output feeds harness/gate.py's G4 check.

    python harness/vacuity.py

Expect this to be uncomfortable. The point of running it is to find out which of our own properties
cannot fail, and we would rather find that ourselves than have it pointed out.
"""
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
import corpus    # noqa: E402  (reuse its verified activation helper and mutant definitions)
import runlock   # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WOO = os.path.join(RIG, "plugin", "razorpay-woocommerce", "includes", "razorpay-webhook.php")

# Variants to run the FULL property suite against. Each is (key, find, replace, note).
# `None` means the unmodified plugin.
VARIANTS = [
    ("baseline", None, None,
     "razorpay-woocommerce v4.8.7, unmodified"),

    ("p1-repaired",
     """        // If it is already marked as unpaid, ignore the event
        if ($order->needs_payment() === true) {
            return;
        }""",
     """        // VARIANT p1-repaired: let the refund proceed regardless of settlement order.
        // Diagnostic only -- see harness/causality.py for why this is not a proposed fix.
        if (false && $order->needs_payment() === true) {
            return;
        }""",
     "the ordering guard disabled -- P1 should become GREEN here"),

    # P2 reported GREEN on every variant above, which makes it VACUOUS: we had never observed it
    # fail, so a GREEN was not evidence of anything. This variant exists purely to answer "can P2
    # fail at all?".
    #
    # Measuring it first taught us something: the plugin IS idempotent on refunds, but not because
    # it checks. Its "already refunded" branch logs and falls through without returning; what
    # actually prevents a second refund is WooCommerce refusing to over-refund an order. So the
    # idempotence is inherited from the host, not implemented by the integration.
    #
    # This mutant makes each refund small enough that WooCommerce's over-refund guard never fires.
    # If P2 stays GREEN through that, P2 cannot detect double-refunding and should not be shipped.
    ("p2-nonidempotent-refund",
     "        $refundAmount = round(($data['payload']['refund']['entity']['amount'] / 100), 2);",
     """        // VARIANT p2-nonidempotent-refund: refund a token amount so WooCommerce's
        // over-refund guard never trips, exposing the missing check in the plugin itself.
        $refundAmount = 1.00;""",
     "refunds a token amount -- P2 should become RED if it can detect double-refunding"),
]


def run_suite():
    """Run check.py and parse the per-property verdicts out of its summary block."""
    p = subprocess.run([sys.executable, "-u", os.path.join(HERE, "check.py")],
                       capture_output=True, text=True, timeout=3600)
    out = (p.stdout or "") + (p.stderr or "")
    verdicts = {}
    for line in out.splitlines():
        s = line.strip()
        for key in ("P1-ORDER-INDEPENDENCE", "P2-DUPLICATE-TOLERANCE",
                    "P3-EVENT-ID-DEDUP", "P4-NO-SILENT-LOSS", "P5-AMOUNT-INTEGRITY"):
            if s.startswith(key):
                verdicts[key] = s.split()[-1]
    return verdicts, out


def main():
    print("=" * 100)
    print("VACUITY CHECK -- can each property actually fail?")
    print("=" * 100)
    print("%d variants x the full property suite. Roughly 2 minutes each.\n" % len(VARIANTS))

    corpus.activate("woocommerce")
    original = io.open(WOO, encoding="utf-8").read()
    per_variant = {}

    try:
        for key, find, repl, note in VARIANTS:
            if find and find not in original:
                print("  %-14s SKIPPED -- anchor absent (plugin changed?)" % key)
                continue
            io.open(WOO, "w", encoding="utf-8", newline="\n").write(
                original.replace(find, repl, 1) if find else original)
            print("  %-14s %s" % (key, note))
            t0 = time.time()
            v, _ = run_suite()
            per_variant[key] = v
            print("      %s   (%.0fs)" % (
                "  ".join("%s=%s" % (k.split("-")[0], x) for k, x in sorted(v.items())),
                time.time() - t0))
    finally:
        io.open(WOO, "w", encoding="utf-8", newline="\n").write(original)
        print("\n  plugin restored to unmodified")

    # A property is falsifiable if SOME variant made it RED.
    props = sorted({k for v in per_variant.values() for k in v})

    # REFUSE TO CONCLUDE FROM NOTHING.
    # The first version of this script parsed zero verdicts -- a lock deadlock killed every child
    # run in 0 seconds -- and then printed "Every property was violated by at least one variant",
    # which was VACUOUSLY TRUE over an empty set. A vacuity checker that passes vacuously is
    # precisely the failure it exists to catch. An empty or single-variant result is now a hard
    # error rather than a summary.
    if not props:
        raise SystemExit(
            "REFUSING TO REPORT: no property verdicts were parsed from any variant.\n"
            "  Every child run produced nothing, so there is no evidence to summarise.\n"
            "  Check that `python harness/check.py` runs standalone, and that the rig lock is not\n"
            "  blocking the child (see harness/runlock.py).")
    if len(per_variant) < 2:
        raise SystemExit(
            "REFUSING TO REPORT: only %d variant produced verdicts. Falsifiability needs at least\n"
            "  two, or 'never RED' cannot be distinguished from 'never run'." % len(per_variant))
    print("\n" + "=" * 100)
    print("FALSIFIABILITY")
    print("=" * 100)
    print("  %-24s %-34s %s" % ("PROPERTY", "VERDICTS SEEN", "STATUS"))
    summary = {}
    for p in props:
        seen = {v.get(p) for v in per_variant.values() if v.get(p)}
        red = "RED" in seen
        status = "falsifiable" if red else "** VACUOUS -- cannot fail **"
        summary[p] = {"seen": sorted(seen), "falsifiable": red}
        print("  %-24s %-34s %s" % (p, ", ".join(sorted(seen)), status))

    vacuous = [p for p, s in summary.items() if not s["falsifiable"]]
    print()
    if vacuous:
        print("  %d propert%s cannot fail on any variant tested:" % (len(vacuous), "y" if len(vacuous) == 1 else "ies"))
        for p in vacuous:
            print("    - %s" % p)
        print("  A property that cannot fail is not evidence that the integration is correct.")
        print("  Either find a variant that violates it, or report it as untested. Do not count it.")
    else:
        print("  Every property was violated by at least one variant.")
    print("=" * 100)

    # Shape the output for gate.py's G4: mutant -> {property: verdict}
    dest = os.path.join(ROOT, "spec", "property_mutants.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    io.open(dest, "w", encoding="utf-8").write(json.dumps(per_variant, indent=2))
    io.open(os.path.join(ROOT, "spec", "vacuity.json"), "w", encoding="utf-8").write(
        json.dumps(summary, indent=2))
    print("saved -> spec/property_mutants.json  (feeds gate.py G4)")
    print("saved -> spec/vacuity.json")
    return 1 if vacuous else 0


if __name__ == "__main__":
    try:
        with runlock.exclusive("vacuity"):
            sys.exit(main())
    except runlock.RigBusy as e:
        print("REFUSING TO START.")
        print(e)
        sys.exit(2)
