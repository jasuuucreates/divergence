#!/usr/bin/env python
"""
Stage 2 of the regression range: confirm the static screen by EXECUTION.

harness/regression.py screens 139 tagged releases with a static predicate and reports that C6 is
present in all 111 decidable ones, back to 1.6.0-beta (2017-08-08). That is a grep with a date
attached, and this project's whole argument is that a grep is the weak form of the evidence.

So this checks out an OLD release into the rig and runs the actual property against it. If a
nine-year-old version behaves the same way the current one does, the claim stops being about text
and becomes about behaviour.

Two honest caveats, both reported rather than hidden:
  * An old plugin running under modern WooCommerce and PHP 8.2 is not the environment it shipped
    into. If it fails to run, that is a fact about our rig, not a finding about the plugin, and it
    is reported as UNDECIDABLE rather than as a pass.
  * The screen and the confirmation can disagree. If they do, the screen is wrong and the
    disagreement is the interesting result.

    python harness/confirm_range.py --tag v4.0.0

Restores the working tree to the pinned version afterwards, and verifies it.
"""
import argparse
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RIG = os.path.join(ROOT, "rig")
PLUGIN = os.path.join(RIG, "plugin", "razorpay-woocommerce")

sys.path.insert(0, HERE)
import corpus    # noqa: E402
import runlock   # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PINNED = "v4.8.7"


def git(*args, cwd=PLUGIN):
    p = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def run_p5():
    """Run the amount-integrity probe and return its verdict."""
    p = subprocess.run([sys.executable, "-u", os.path.join(HERE, "amount_integrity.py")],
                       capture_output=True, text=True, timeout=1800)
    out = (p.stdout or "") + (p.stderr or "")
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("RED --"):
            return "RED", out
        if s.startswith("GREEN --"):
            return "GREEN", out
        if s.startswith("UNDECIDABLE"):
            return "UNDECIDABLE", out
    return "UNDECIDABLE", out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="v4.0.0", help="the historical release to confirm against")
    a = ap.parse_args()

    print("=" * 96)
    print("REGRESSION CONFIRMATION -- does an OLD release actually behave the same way?")
    print("=" * 96)

    rc, _, _ = git("rev-parse", "--git-dir")
    if rc != 0:
        raise SystemExit("rig/plugin/razorpay-woocommerce is not a git checkout. Run rig/setup.sh.")

    # A shallow clone has no history, so fetch just the tag we need.
    print("  fetching %s ..." % a.tag)
    rc, _, err = git("fetch", "--depth", "1", "origin", "tag", a.tag)
    if rc != 0:
        raise SystemExit("could not fetch %s: %s" % (a.tag, err[:200]))

    corpus.activate("woocommerce")
    results = {}
    try:
        for tag in (PINNED, a.tag):
            rc, _, err = git("checkout", "-q", "--detach", tag)
            if rc != 0:
                print("  %-10s CHECKOUT FAILED: %s" % (tag, err[:80]))
                results[tag] = {"verdict": "UNDECIDABLE", "why": "checkout failed"}
                continue
            _, sha, _ = git("rev-parse", "--short", "HEAD")
            verdict, out = run_p5()
            results[tag] = {"verdict": verdict, "sha": sha}
            print("  %-10s (%s)  P5 = %s" % (tag, sha, verdict))
            if verdict == "UNDECIDABLE":
                print("      the probe produced no verdict. That is a fact about this rig running a")
                print("      historical plugin under modern WooCommerce/PHP, not a finding about the")
                print("      plugin. Reported as undecidable.")
    finally:
        git("checkout", "-q", "--detach", PINNED)
        _, sha, _ = git("rev-parse", "--short", "HEAD")
        print("\n  restored to %s (%s)" % (PINNED, sha))

    print("\n" + "=" * 96)
    now = results.get(PINNED, {}).get("verdict")
    then = results.get(a.tag, {}).get("verdict")
    if now == then == "RED":
        print("CONFIRMED BEHAVIOURALLY: %s and %s both reach a paid state on a mismatched amount."
              % (a.tag, PINNED))
        print("  The static screen said the defect is present in every decidable release back to")
        print("  1.6.0-beta (2017-08-08). This is that claim checked by execution at one point in")
        print("  the range, rather than asserted from source alone.")
    elif "UNDECIDABLE" in (now, then):
        print("UNDECIDABLE: one of the two versions did not produce a verdict in this rig.")
        print("  The static screen stands on its own terms; the behavioural confirmation does not.")
        print("  Report the screen as static-only rather than implying it was executed.")
    else:
        print("DISAGREEMENT: %s=%s and %s=%s." % (a.tag, then, PINNED, now))
        print("  The static predicate and the executed property disagree. The predicate is wrong.")
        print("  This is the interesting outcome -- investigate before publishing either.")
    print("=" * 96)

    out = os.path.join(ROOT, "spec", "regression_confirm.json")
    io.open(out, "w", encoding="utf-8").write(json.dumps(
        {"pinned": PINNED, "historical": a.tag, "results": results}, indent=2))
    print("saved -> %s" % os.path.relpath(out, ROOT))


if __name__ == "__main__":
    try:
        with runlock.exclusive("regression"):
            main()
    except runlock.RigBusy as e:
        print("REFUSING TO START.")
        print(e)
        sys.exit(2)
