#!/usr/bin/env python
"""
The held-out corpus: does the harness actually detect what it claims to?

A detector that reports RED on code we already knew was broken proves very little. The question a
reviewer will ask is whether the verdict TRACKS THE DEFECT -- whether it goes GREEN when the defect
is absent and RED when it is present, on code the harness has not been tuned against.

So this builds a 2xN corpus by mutating BOTH targets in BOTH directions:

  REPAIR mutants  -- take the DEFECTIVE plugin and fix the defect.
                     The harness must flip RED -> GREEN. A failure here is a FALSE POSITIVE:
                     the harness is reporting a defect that is no longer there.

  INJECT mutants  -- take the CORRECT plugin and introduce the defect.
                     The harness must flip GREEN -> RED. A failure here is a FALSE NEGATIVE:
                     the harness misses a defect it claims to detect.

Injecting into razorpay-edd matters more than repairing razorpay-woocommerce, because EDD is code the
harness was never tuned against. A detector that only works on the codebase it was developed on is
not a detector.

Every mutant is a single, minimal, reversible edit. The file's sha256 is recorded before, during and
after, and the original bytes are restored in a finally block, so a reviewer can confirm nothing was
left behind.

HONEST LIMITATION, to be repeated wherever these numbers appear: this corpus is SELF-AUTHORED. We can
only measure detection of defect classes we thought of. Razorpay's own AI playbook calls this a
"cold-start set" and endorses building one from domain expertise before production traces exist --
but naming the practice does not remove the circularity. The corpus, the seeds and the false-positive
count are all published so the measurement can be disputed on its merits.
"""
import argparse
import hashlib
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
import dockerenv  # noqa: E402
import runlock    # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WOO = os.path.join(RIG, "plugin", "razorpay-woocommerce", "includes", "razorpay-webhook.php")
EDD = os.path.join(RIG, "plugin", "razorpay-edd", "includes", "razorpay-webhook.php")


class Mutant:
    """One minimal, reversible edit, with the verdict it is expected to produce."""

    def __init__(self, key, kind, target, path, find, replace, prop, expect, why):
        self.key = key
        self.kind = kind            # "repair" | "inject" | "control"
        self.target = target        # "woocommerce" | "edd"
        self.path = path
        self.find = find
        self.replace = replace
        self.prop = prop            # property whose verdict should move
        self.expect = expect        # verdict the harness SHOULD return once applied
        self.why = why


MUTANTS = [
    # ---------------- controls: no edit at all -------------------------------------------
    Mutant("control-woo-baseline", "control", "woocommerce", WOO, None, None,
           "P5-AMOUNT-INTEGRITY", "RED",
           "Unmodified WooCommerce. Establishes the baseline the repair mutants move away from."),
    Mutant("control-edd-baseline", "control", "edd", EDD, None, None,
           "P5-AMOUNT-INTEGRITY", "GREEN",
           "Unmodified EDD. Establishes that the harness does not simply always report RED."),

    # ---------------- INJECT into EDD: the harder direction -------------------------------
    # EDD is code the harness was never tuned against. If a defect injected here is missed,
    # the harness only works on its development codebase.
    Mutant("inject-edd-drop-amount-check", "inject", "edd", EDD,
           "        if($payment['amount'] === $amount)",
           "        if(true) // MUTANT inject-edd-drop-amount-check: amount comparison removed",
           "P5-AMOUNT-INTEGRITY", "RED",
           "Removes EDD's amount comparison at razorpay-webhook.php:130. This is exactly the defect "
           "WooCommerce has. If the harness does not flip GREEN->RED here it cannot detect the "
           "defect class at all -- it merely recognises WooCommerce."),

    # ---------------- REPAIR WooCommerce: the false-positive check ------------------------
    Mutant("repair-woo-add-amount-check", "repair", "woocommerce", WOO,
           """        if ($payment['status'] === 'captured') {
            $success = true;""",
           """        if ($payment['status'] === 'captured' and (int) $payment['amount'] === (int) $amount) {
            $success = true;  // MUTANT repair-woo-add-amount-check: enforce paid == ordered""",
           "P5-AMOUNT-INTEGRITY", "GREEN",
           "Adds the comparison WooCommerce is missing, mirroring what its own virtual-account path "
           "and razorpay-edd already do. If the harness still reports RED, it is reporting a defect "
           "that is no longer present -- a false positive."),

    # ---------------- SUBTLE injections: a defect that still LOOKS like a check ------------
    # A detector that only notices a deleted line is a diff viewer. These keep a comparison in
    # place and make it vacuous, which is how this class of bug actually reaches production.
    Mutant("inject-edd-self-compare", "inject", "edd", EDD,
           "        if($payment['amount'] === $amount)",
           "        if($payment['amount'] === $payment['amount']) // MUTANT inject-edd-self-compare",
           "P5-AMOUNT-INTEGRITY", "RED",
           "The comparison is still there and still reads like a check, but compares the value to "
           "itself so it is always true. Grep-based tooling sees a comparison and passes it. Only "
           "executing the code with a mismatched amount distinguishes this from the real check."),

    Mutant("inject-edd-compare-to-paid", "inject", "edd", EDD,
           "        $amount = $this->getOrderAmountAsInteger($order);",
           "        $amount = (int) $payment['amount']; // MUTANT inject-edd-compare-to-paid",
           "P5-AMOUNT-INTEGRITY", "RED",
           "Leaves the comparison untouched and corrupts what it compares against: the expected "
           "amount is taken from the payment instead of the order. The check now proves nothing. "
           "This is the shape a real refactoring accident takes."),

    # ---------------- OVER-SENSITIVITY controls: changes that must NOT move the verdict ----
    # If an irrelevant edit flips a verdict, the harness is measuring something other than the
    # property it names, and every other result is suspect.
    Mutant("noise-edd-log-text", "control", "edd", EDD,
           "'EDD_ERROR: Payment to Razorpay Failed. Amount mismatch.'",
           "'EDD_ERROR: rig noise mutant -- wording changed, behaviour identical.'",
           "P5-AMOUNT-INTEGRITY", "GREEN",
           "Changes only a log string. The verdict must not move. A harness that reacts to this is "
           "keying on text rather than on behaviour."),

    Mutant("noise-woo-comment", "control", "woocommerce", WOO,
           "        // If it is already marked as unpaid, ignore the event",
           "        // MUTANT noise-woo-comment: comment reworded, behaviour identical",
           "P5-AMOUNT-INTEGRITY", "RED",
           "Reworded comment only. WooCommerce's P5 baseline must stay RED. Confirms the verdict "
           "is stable under edits that change no behaviour."),
]


def sha(path):
    return hashlib.sha256(io.open(path, "rb").read()).hexdigest()[:16]


def run_probe(target):
    """Run the smallest probe that decides P5 for this target."""
    script = "amount_integrity.py" if target == "woocommerce" else "edd_probe.py"
    p = subprocess.run([sys.executable, "-u", os.path.join(HERE, script)],
                       capture_output=True, text=True, timeout=1800)
    out = (p.stdout or "") + (p.stderr or "")

    # Same rule as matrix.py: a probe that disowned its own result must not have that result read
    # back out of its stdout. edd_probe.py prints "CONTROL FAILED ... nothing below is trustworthy"
    # and then prints its verdict line anyway, so scanning for the verdict alone would score a
    # mutant against a dead endpoint -- and this module is what measures whether the harness can
    # detect anything at all.
    if "CONTROL FAILED" in out or "UNDECIDABLE" in out:
        return "UNDECIDABLE", out

    for line in out.splitlines():
        s = line.strip()
        if s.startswith("RED --") or "P5-AMOUNT-INTEGRITY: RED" in s:
            return "RED", out
        if s.startswith("GREEN --") or "P5-AMOUNT-INTEGRITY: GREEN" in s:
            return "GREEN", out
    return "UNKNOWN", out


def activate(target):
    """Make exactly one gateway plugin active, and VERIFY it.

    Two things bit here and both failed silently:
      * razorpay-woocommerce depends on woocommerce, so woocommerce must be activated FIRST.
        Activating them in the wrong order leaves razorpay-woocommerce inactive, with a non-zero
        exit nobody was reading.
      * A probe run against the wrong active plugin set does not error cleanly -- new_order.php
        simply cannot find wc_create_order and the run dies with a KeyError that reads like a
        harness bug rather than a setup bug.

    So this asserts the final state instead of assuming it. A corpus row whose setup silently
    failed is worse than a missing row: it looks like a measurement.
    """
    e = dockerenv.shell()

    def wp(*args):
        return subprocess.run(["docker", "compose", "run", "--rm", "-T", "cli", "wp"] + list(args),
                              cwd=RIG, env=e, capture_output=True, text=True, timeout=600)

    if target == "woocommerce":
        off, on = ["razorpay-edd"], ["woocommerce", "razorpay-woocommerce"]   # order matters
    else:
        off, on = ["razorpay-woocommerce", "woocommerce"], ["razorpay-edd"]

    wp("plugin", "deactivate", *off)
    for name in on:                      # one at a time, dependency order preserved
        wp("plugin", "activate", name)

    got = wp("plugin", "list", "--status=active", "--field=name").stdout or ""
    active = {l.strip() for l in got.splitlines()
              if l.strip() and not l.startswith(("Warning", "["))}
    missing = [n for n in on if n not in active]
    if missing:
        raise RuntimeError("activation failed for %s (active: %s). Refusing to measure."
                           % (missing, sorted(active)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="run only these mutant keys")
    ap.add_argument("--out", default=os.path.join(RIG, "out", "corpus.json"))
    a = ap.parse_args()

    plan = [m for m in MUTANTS if not a.only or m.key in a.only]
    print("=" * 100)
    print("MUTATION CORPUS -- does the verdict track the defect?")
    print("=" * 100)
    print("%d mutants: %d control, %d inject, %d repair\n"
          % (len(plan),
             sum(1 for m in plan if m.kind == "control"),
             sum(1 for m in plan if m.kind == "inject"),
             sum(1 for m in plan if m.kind == "repair")))

    rows = []
    for m in plan:
        original = io.open(m.path, encoding="utf-8").read()
        sha_before = sha(m.path)
        if m.find and m.find not in original:
            print("  %-32s SKIPPED -- anchor not found (plugin changed?)" % m.key)
            rows.append({"mutant": m.key, "result": "SKIPPED", "reason": "anchor absent"})
            continue
        print("  %-32s [%s/%s] expect %s" % (m.key, m.kind, m.target, m.expect))
        t0 = time.time()
        try:
            if m.find:
                io.open(m.path, "w", encoding="utf-8", newline="\n").write(
                    original.replace(m.find, m.replace, 1))
            activate(m.target)
            got, _ = run_probe(m.target)
        finally:
            io.open(m.path, "w", encoding="utf-8", newline="\n").write(original)
        ok = (got == m.expect)
        print("      -> observed %-8s %s   (%.0fs)"
              % (got, "MATCH" if ok else "*** MISMATCH ***", time.time() - t0))
        # Compare the restore against the sha captured BEFORE the edit. Recording the restored
        # sha on its own proved nothing -- the same shape as causality.py's sha(x) == sha(x), which
        # was a restore check that could not fail. This module edits the vendor plugin eight times
        # in a row; a restore that silently did not restore would make every later mutant a
        # measurement of the previous mutant's leftovers.
        sha_after = sha(m.path)
        if sha_after != sha_before:
            raise RuntimeError(
                "RESTORE FAILED after mutant %s: %s is not the file we started from "
                "(before %s, after %s). Refusing to continue -- every later row would be "
                "measured against a corrupted plugin. Restore it: cd rig && bash setup.sh"
                % (m.key, m.path, sha_before, sha_after))
        rows.append({"mutant": m.key, "kind": m.kind, "target": m.target,
                     "property": m.prop, "expected": m.expect, "observed": got,
                     "match": ok, "why": m.why,
                     "sha_before": sha_before, "sha_restored": sha_after,
                     "restore_verified": True})

    scored = [r for r in rows if r.get("observed") in ("RED", "GREEN")]
    tp = sum(1 for r in scored if r["expected"] == "RED" and r["observed"] == "RED")
    fn = sum(1 for r in scored if r["expected"] == "RED" and r["observed"] == "GREEN")
    tn = sum(1 for r in scored if r["expected"] == "GREEN" and r["observed"] == "GREEN")
    fp = sum(1 for r in scored if r["expected"] == "GREEN" and r["observed"] == "RED")

    print("\n" + "=" * 100)
    print("CONFUSION MATRIX (n=%d scored)" % len(scored))
    print("  true positives  %d   (defect present, harness said RED)" % tp)
    print("  false negatives %d   (defect present, harness said GREEN)  <- missed defects" % fn)
    print("  true negatives  %d   (defect absent,  harness said GREEN)" % tn)
    print("  false positives %d   (defect absent,  harness said RED)    <- accuses correct code" % fp)
    if tp + fn:
        print("  recall    %.2f" % (tp / float(tp + fn)))
    if tp + fp:
        print("  precision %.2f" % (tp / float(tp + fp)))
    print("\n  n is small and the corpus is self-authored. These numbers bound the harness's")
    print("  behaviour on the defect classes we thought of; they are not a population estimate.")
    print("=" * 100)

    # An unscored row is not a passing row. Dropping UNKNOWN/UNDECIDABLE from the matrix and then
    # exiting 0 meant this gate was satisfiable by measuring NOTHING: every mutant failing to
    # produce a verdict yielded fp=0, fn=0, and a clean exit -- a green CI badge on our own
    # detection metric, earned by a run that detected nothing. Refuse unless every planned mutant
    # actually produced a verdict.
    unscored = [r for r in rows if r.get("observed") not in ("RED", "GREEN")]
    if unscored or len(scored) != len(rows) or not scored:
        print("\n" + "!" * 100)
        print("GATE FAILED: %d of %d mutants produced no usable verdict." % (len(unscored), len(rows)))
        for r in unscored:
            print("    %-40s observed=%s" % (r.get("mutant", r.get("property", "?")), r.get("observed")))
        print("  A mutant that could not be scored is not a mutant that passed. These numbers do")
        print("  not bound anything until every planned mutant returns RED or GREEN.")
        print("!" * 100)
        io.open(a.out, "w", encoding="utf-8").write(json.dumps(
            {"rows": rows, "tp": tp, "fn": fn, "tn": tn, "fp": fp,
             "unscored": len(unscored), "gate": "FAILED"}, indent=2))
        return 1

    io.open(a.out, "w", encoding="utf-8").write(json.dumps(
        {"rows": rows, "tp": tp, "fn": fn, "tn": tn, "fp": fp,
         "unscored": 0, "gate": "PASSED"}, indent=2))
    print("saved -> %s" % os.path.normpath(a.out))
    # The full pass condition, restated in the exit expression itself. The early return above
    # already refuses an unscored run; encoding it here too means the process exit code can never
    # drift away from the gate, and a reader checking "what makes this exit 0" sees all of it.
    return 1 if (fp or fn or unscored or not scored) else 0


if __name__ == "__main__":
    try:
        with runlock.exclusive("corpus"):
            sys.exit(main())
    except runlock.RigBusy as e:
        print("REFUSING TO START.")
        print(e)
        sys.exit(2)
