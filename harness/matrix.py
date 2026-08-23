#!/usr/bin/env python
"""
The two-target matrix, in one command.

This is the headline artefact: the same harness, the same property, the same underpaid delivery,
against two of the payment provider's own official plugins -- one of which gets it right.

Why it is worth a script of its own rather than a paragraph in the README: the objection this project
has to survive is "you wrote a script that prints your own bugs." A single command that produces
RED for one target and GREEN for another, with the expectations registered beforehand, answers that
better than any amount of prose.

    python harness/matrix.py

Only one gateway plugin can be active at a time -- both define the same PHP constants -- so this
switches between them and asserts the switch actually took effect before measuring anything.
A row measured against the wrong active plugin is not a failed row, it is a fabricated one.
"""
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RIG = os.path.join(os.path.dirname(HERE), "rig")

sys.path.insert(0, HERE)
import corpus     # noqa: E402  (reuses its verified plugin-activation helper)
import runlock    # noqa: E402
import targets    # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROBE = {"woocommerce": "amount_integrity.py", "edd": "edd_probe.py"}


def measure(target):
    """Run the smallest probe that decides P5 for this target, after verifying activation."""
    corpus.activate(target)                      # raises rather than measuring the wrong plugin
    p = subprocess.run([sys.executable, "-u", os.path.join(HERE, PROBE[target])],
                       capture_output=True, text=True, timeout=1800)
    out = (p.stdout or "") + (p.stderr or "")
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("RED --") or "P5-AMOUNT-INTEGRITY: RED" in s:
            return "RED", out
        if s.startswith("GREEN --") or "P5-AMOUNT-INTEGRITY: GREEN" in s:
            return "GREEN", out
    return "UNKNOWN", out


def main():
    print("=" * 96)
    print("TWO-TARGET MATRIX -- P5 AMOUNT INTEGRITY")
    print("=" * 96)
    print("Same harness. Same property. Same underpaid delivery (Rs 1 against a Rs 499 order).\n")

    rows = []
    for key in ("woocommerce", "edd"):
        t = targets.ALL[key]
        predicted = targets.expectations(t)["P5-AMOUNT-INTEGRITY"]
        print("  %-14s %s @ %s" % (key, t.repo, t.ref))
        print("     amount check : %s" % (t.verifies_amount_at or "ABSENT on the main payment path"))
        print("     predicted    : %s" % predicted)
        t0 = time.time()
        got, _ = measure(key)
        agree = (got == predicted)
        print("     observed     : %-6s %s   (%.0fs)\n"
              % (got, "MATCH" if agree else "*** MISMATCH -- investigate before claiming ***",
                 time.time() - t0))
        rows.append({"target": key, "repo": t.repo, "ref": t.ref,
                     "amount_check": t.verifies_amount_at, "predicted": predicted,
                     "observed": got, "match": agree})

    print("=" * 96)
    print("  %-24s %-10s %s" % ("TARGET", "VERDICT", "AMOUNT CHECK"))
    for r in rows:
        print("  %-24s %-10s %s" % (r["target"], r["observed"],
                                    r["amount_check"] or "absent on the main path"))
    print("=" * 96)

    verdicts = {r["observed"] for r in rows}
    if verdicts == {"RED", "GREEN"}:
        print("The harness DISCRIMINATES: it reports a defect in one implementation and clears the")
        print("other. A harness that returns RED for every target is a bug list, not an oracle.")
    elif verdicts == {"RED"}:
        print("Both targets RED. Either both are genuinely defective, or the harness is not")
        print("discriminating -- and the second is the more likely explanation. Investigate before")
        print("publishing anything from this run.")
    else:
        print("Unexpected verdict set: %s. Do not publish until this is understood." % sorted(verdicts))

    out = os.path.join(RIG, "out", "matrix.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    io.open(out, "w", encoding="utf-8").write(json.dumps(rows, indent=2))
    print("\nsaved -> %s" % os.path.normpath(out))
    return 0 if all(r["match"] for r in rows) else 1


if __name__ == "__main__":
    try:
        with runlock.exclusive("matrix"):
            sys.exit(main())
    except runlock.RigBusy as e:
        print("REFUSING TO START.")
        print(e)
        sys.exit(2)
