#!/usr/bin/env python
"""
What does a GREEN from the schedule search actually cover?

Today `search.py` reports "64 schedules ran and 16 of 20 multisets agreed". That is a statement about
how many things we happened to execute. A model checker makes a different and much stronger kind of
statement: it reports how many EQUIVALENCE CLASSES it covered, under a stated relation, so that a
GREEN means "no divergence exists in this space", not "no divergence appeared in our sample".

Nidhugg prints `Trace count:` rather than a run count for exactly this reason
(nidhugg/src/main.cpp), and loom's entire claim is "exhaustive under these named bounds"
(loom/src/model.rs: DEFAULT_MAX_BRANCHES, preemption_bound).

This module buys the cheapest honest version of that claim. It does not build access-set
instrumentation or a full Mazurkiewicz quotient -- those are real, and out of scope here. It does one
thing properly:

    Some events in the alphabet are UNITS: they change nothing observable, so inserting one anywhere
    in a sequence cannot change the terminal state. If an event is a unit, every sequence containing
    it is equivalent to the same sequence with it deleted, and the space collapses.

razorpay-webhook.php's paymentFailed() is literally `{ return; }`, which makes payment.failed a
candidate unit by inspection. **Inspection is not evidence.** This module VERIFIES unit-hood by
execution before using it, and refuses to claim any reduction it has not measured.

    python harness/coverage.py           # verify units, then print the certificate
"""
import io
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

sys.path.insert(0, HERE)
import corpus    # noqa: E402  (for its verified activation helper)
import measured  # noqa: E402
import rig       # noqa: E402
import runlock   # noqa: E402
import search     # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ALPHABET = search.ALPHABET
BASE = ["payment.authorized", "refund.created"]   # a sequence known to reach a definite state


def is_unit(event, repeats=2):
    """Does inserting this event anywhere leave the terminal state unchanged?

    Tested at every insertion position, not just one, because an event that is inert at the end can
    still matter at the start -- and a unit claim that only holds in one position is not a unit
    claim. Every trial is asserted to have measured something first, so an all-None run cannot be
    mistaken for 'no change'.
    """
    baseline = rig.trial(list(BASE))
    measured.require([baseline], "order_status")
    ref = baseline["terminal"]["order_status"]

    positions = []
    for i in range(len(BASE) + 1):
        seq = BASE[:i] + [event] + BASE[i:]
        t = rig.trial(seq)
        measured.require([t], "order_status")
        got = t["terminal"]["order_status"]
        positions.append({"at": i, "sequence": seq, "terminal": got, "same": got == ref})
        print("      insert at %d -> %-16s %s" % (i, got, "same" if got == ref else "DIFFERENT"))
    return all(p["same"] for p in positions), ref, positions


def classes(alphabet, length, units):
    """Distinct sequences after deleting every unit. Units are deletable, so two sequences that
    differ only in units are the same execution."""
    reps = {}
    for s in itertools.product(alphabet, repeat=length):
        key = tuple(e for e in s if e not in units)
        reps.setdefault(key, []).append(list(s))
    return reps


def main():
    print("=" * 96)
    print("COVERAGE CERTIFICATE -- what does a GREEN from the schedule search actually cover?")
    print("=" * 96)
    print("alphabet: %s\n" % ", ".join(ALPHABET))

    # Activate the target explicitly and verify it took. Assuming the right plugin is already
    # active is how five separate runs died on an unreadable KeyError instead of a setup message.
    corpus.activate("woocommerce")

    units, evidence = [], {}
    for e in ALPHABET:
        if e in BASE:
            continue     # an event the baseline depends on cannot be tested for unit-hood this way
        print("  testing whether %s is a unit (inert at every position):" % e)
        ok, ref, positions = is_unit(e)
        evidence[e] = {"is_unit": ok, "reference_terminal": ref, "positions": positions}
        print("      -> %s\n" % ("UNIT -- deletable from any sequence" if ok
                                 else "not a unit -- it changes something"))
        if ok:
            units.append(e)

    print("=" * 96)
    for L in (2, 3, 4, 5, 6):
        total = len(ALPHABET) ** L
        reps = classes(ALPHABET, L, set(units))
        print("  length %d : %6d orderings -> %5d classes after deleting %s   (%.0fx fewer trials)"
              % (L, total, len(reps), units or "nothing", total / float(len(reps))))
    print("=" * 96)

    L = 3
    reps = classes(ALPHABET, L, set(units))
    cert = {
        "alphabet": ALPHABET,
        "length": L,
        "total_orderings": len(ALPHABET) ** L,
        "equivalence_classes": len(reps),
        "units": units,
        "unit_basis": "verified by execution, every insertion position -- see unit_evidence",
        "unit_evidence": evidence,
        "caveat": (
            "Unit-hood is OBSERVED, not proved. It was established by executing the event at every "
            "insertion position in a two-event baseline and finding the terminal state unchanged. "
            "An event that is inert with respect to the states this rig observes could still have "
            "an effect the rig does not observe -- a transient, an option, an outbound request. "
            "The reduction is therefore a measured claim about this rig's observables, not a "
            "theorem about the plugin."),
    }
    print("\nCERTIFICATE (length %d):" % L)
    print("  %d orderings over %d events collapse to %d classes after deleting %s."
          % (cert["total_orderings"], len(ALPHABET), cert["equivalence_classes"],
             ", ".join(units) if units else "nothing"))
    print("  A GREEN at this length therefore covers %d orderings, not %d runs."
          % (cert["total_orderings"], cert["equivalence_classes"]))
    print("\n  %s" % cert["caveat"])

    out = os.path.join(ROOT, "rig", "out", "coverage.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    io.open(out, "w", encoding="utf-8").write(json.dumps(cert, indent=2))
    print("\nsaved -> %s" % os.path.relpath(out, ROOT))
    return 0


if __name__ == "__main__":
    try:
        with runlock.exclusive("coverage"):
            sys.exit(main())
    except runlock.RigBusy as e:
        print("REFUSING TO START.")
        print(e)
        sys.exit(2)
