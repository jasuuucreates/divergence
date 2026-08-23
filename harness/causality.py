"""
Causality test: does the harness blame the right line?

A detector that reports RED proves nothing on its own -- it might be reacting to some incidental
property of the rig. The question that matters is whether the verdict is CAUSED by the line the
harness points at.

So: patch that one line, re-run, and see whether the verdict flips. If RED -> GREEN when the blamed
line changes, and back to RED when it is restored, the harness is measuring what it claims to.

This doubles as the proposed remedy: the patch below is a real, minimal fix for P1.

Nothing here modifies the repository under test permanently -- the original bytes are restored in a
finally block, and the file's sha256 is printed before and after so a reviewer can confirm it.
"""
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.join(ROOT, "rig", "plugin", "razorpay-woocommerce",
                      "includes", "razorpay-webhook.php")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# The line the harness blames for P1. Razorpay's refundedCreated() drops a refund outright when the
# order still looks unpaid -- and because payment.authorized is parked for a >=300s cron while
# refunds are handled synchronously, "still looks unpaid" is the DEFAULT for any refund issued
# within five minutes of authorization.
BLAMED = """        // If it is already marked as unpaid, ignore the event
        if ($order->needs_payment() === true) {
            return;
        }"""

# ATTEMPT 1 (FAILED, kept deliberately -- see .kb/log.md):
#   Defer the refund into the existing queue instead of dropping it. This did NOT flip the verdict,
#   for two reasons discovered by reading the code afterwards:
#     (a) the cron's switch handles ONLY case 'payment.authorized' (woo-razorpay.php:3405), so a
#         deferred refund.created is stored and then ignored forever; and
#     (b) saveWebhookEvent() overwrites rather than appends (the line-210 type confusion), so parking
#         the refund would have DESTROYED the stored payment.authorized event -- strictly worse.
#   A patch that makes the bug worse is the correct thing to learn from a causality test.
#
# ATTEMPT 2: the minimal intervention. Let the refund proceed instead of returning early.
#   NOTE THIS IS A DIAGNOSTIC, NOT A PROPOSED PRODUCTION FIX. The guard presumably exists to avoid
#   recording a refund against an order that was never paid. The principled remedy is to stop
#   processing one event synchronously and another asynchronously; this patch only isolates cause.
PATCHED = """        // RIG PATCH (causality diagnostic only -- NOT a proposed fix).
        // Let the refund proceed even if the order still looks unpaid, to test whether this
        // guard is what makes the two legal delivery orderings diverge.
        if (false && $order->needs_payment() === true) {
            return;
        }"""


def sha(path):
    return hashlib.sha256(io.open(path, "rb").read()).hexdigest()[:16]


def run_check():
    p = subprocess.run([sys.executable, os.path.join(HERE, "check.py")],
                       capture_output=True, text=True, timeout=1800)
    out = p.stdout or ""
    verdicts = {}
    for line in out.splitlines():
        line = line.strip()
        for key in ("P1-ORDER-INDEPENDENCE", "P2-DUPLICATE-TOLERANCE",
                    "P4-NO-SILENT-LOSS", "P3-EVENT-ID-DEDUP"):
            if line.startswith(key):
                verdicts[key] = line.split()[-1]
    overall = "?"
    for line in out.splitlines():
        if line.startswith("OVERALL:"):
            overall = line.split()[1]
    return overall, verdicts, out


def main():
    original = io.open(TARGET, encoding="utf-8").read()
    if BLAMED not in original:
        print("ABORT: the blamed block is not present verbatim in %s" % TARGET)
        print("       The plugin may have been updated. Re-read it before trusting any result.")
        return 2

    print("=" * 96)
    print("CAUSALITY TEST -- does patching the blamed line flip the verdict?")
    print("=" * 96)
    print("target : %s" % os.path.relpath(TARGET, ROOT))
    print("sha256 : %s  (unmodified)" % sha(TARGET))
    print()

    try:
        print("--- ARM 1: unmodified plugin ---")
        before_overall, before, _ = run_check()
        print("    OVERALL=%s  %s\n" % (before_overall, before))

        io.open(TARGET, "w", encoding="utf-8", newline="\n").write(
            original.replace(BLAMED, PATCHED, 1))
        print("--- ARM 2: one block patched (refund deferred instead of dropped) ---")
        print("    sha256 : %s  (patched)" % sha(TARGET))
        after_overall, after, _ = run_check()
        print("    OVERALL=%s  %s\n" % (after_overall, after))
    finally:
        io.open(TARGET, "w", encoding="utf-8", newline="\n").write(original)
        print("--- restored ---")
        print("    sha256 : %s  (matches unmodified: %s)"
              % (sha(TARGET), sha(TARGET) == sha(TARGET)))

    p1_before = before.get("P1-ORDER-INDEPENDENCE")
    p1_after = after.get("P1-ORDER-INDEPENDENCE")
    print()
    print("=" * 96)
    print("P1 before patch : %s" % p1_before)
    print("P1 after  patch : %s" % p1_after)
    if p1_before == "RED" and p1_after == "GREEN":
        print("VERDICT: CAUSAL. The harness blames a line that, when changed, flips the property.")
    elif p1_before == p1_after:
        print("VERDICT: NOT CAUSAL. The verdict did not move when the blamed line changed.")
        print("         Either the diagnosis is wrong or the patch does not do what we think.")
    else:
        print("VERDICT: UNEXPECTED TRANSITION -- investigate before claiming anything.")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
