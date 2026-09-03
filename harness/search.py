"""
A SEARCH, not a confirmation.

The objection that decides this project is: "which of these defects did your harness find?"
Everything found so far was found by hand and then encoded, which makes the harness a very good
bug report with a build system around it.

So this does the opposite. It enumerates delivery schedules over the event alphabet the plugin's own
dispatch switch handles, runs every one against a fresh order, and reports any schedule whose
terminal state differs from its peers. Nothing here encodes a defect we already know. The properties
come from contract.py; the schedules come from combinatorics; whatever falls out, the harness found.

Cost note: every trial is a fresh order plus a cron drain, ~12-15s. Length-2 over 4 events is 16
trials (~4 min). Length-3 is 64 (~16 min). Both are affordable; the script prints its plan and its
cost estimate before spending anything, because a search that surprises you with its runtime does not
get run twice.

Determinism: the event alphabet, the ordering of trials and the payment ids are all derived from the
sequence itself, so a given --length run is reproducible. Order ids differ between runs (WooCommerce
assigns them) and are recorded per trial.
"""
import argparse
import itertools
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measured # noqa: E402
import rig      # noqa: E402
import runlock  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Exactly the events razorpay-webhook.php's switch dispatches AND our generator can build.
# Deliberately not a wish-list: an event the generator cannot build faithfully would produce a
# result about our fixture, not about the plugin.
ALPHABET = ["payment.authorized", "payment.failed", "payment.pending", "refund.created"]


def sequences(length, alphabet):
    """All ordered sequences, including repeats -- redelivery is legal input per the vendor."""
    return [list(s) for s in itertools.product(alphabet, repeat=length)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--length", type=int, default=2)
    ap.add_argument("--alphabet", nargs="+", default=ALPHABET)
    ap.add_argument("--limit", type=int, default=0, help="cap trials (0 = no cap)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "..", "rig", "out", "search.json"))
    a = ap.parse_args()

    plan = sequences(a.length, a.alphabet)
    if a.limit:
        plan = plan[:a.limit]

    print("=" * 96)
    print("SCHEDULE SEARCH -- razorpay-woocommerce")
    print("=" * 96)
    print("alphabet : %s" % ", ".join(a.alphabet))
    print("length   : %d" % a.length)
    print("trials   : %d   (~%.0f min at 13s/trial)" % (len(plan), len(plan) * 13 / 60.0))
    print()
    if a.dry_run:
        for s in plan:
            print("   " + " then ".join(s))
        return 0

    results = []
    t0 = time.time()
    for i, seq in enumerate(plan, 1):
        t = rig.trial(seq)
        st = t["terminal"]["order_status"]
        results.append({"sequence": seq, "order": t["order"], "terminal": t["terminal"]})
        print("  [%2d/%d] %-58s -> %s" % (i, len(plan), " then ".join(seq), st))

    # "No divergence found" is a GREEN wearing different words, so it needs the same evidence gate
    # every other verdict in this repo needs. Without this, an unreachable database makes every
    # terminal state None, every multiset collapses to one distinct state, and this module prints
    # "No divergence found ... that is a real result" over a run that measured nothing at all.
    # measured.require raises unless real observations are present.
    measured.require(results, "order_status")

    print("\n" + "=" * 96)
    print("GROUPING BY MULTISET -- schedules with the same events must converge (P1)")
    print("=" * 96)

    by_multiset = {}
    for r in results:
        key = tuple(sorted(r["sequence"]))
        by_multiset.setdefault(key, []).append(r)

    divergent = []
    for key, group in sorted(by_multiset.items()):
        states = {g["terminal"]["order_status"] for g in group}
        flag = "DIVERGES" if len(states) > 1 else "ok"
        if len(states) > 1:
            divergent.append({"multiset": list(key),
                              "outcomes": [{"sequence": g["sequence"],
                                            "terminal": g["terminal"]["order_status"],
                                            "order": g["order"]} for g in group]})
        print("  %-58s %-9s %s" % (" + ".join(key), flag, sorted(x for x in states if x)))

    print("\n" + "=" * 96)
    if divergent:
        print("FOUND %d DIVERGENT MULTISET(S) -- same events, different terminal state:" % len(divergent))
        for d in divergent:
            print("\n  events: %s" % " + ".join(d["multiset"]))
            for o in d["outcomes"]:
                print("    %-56s -> %-16s (order %s)"
                      % (" then ".join(o["sequence"]), o["terminal"], o["order"]))
    else:
        print("No divergence found at length %d over this alphabet." % a.length)
        print("That is a real result: it bounds where the defect is NOT, and it is worth reporting.")
    print("=" * 96)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"alphabet": a.alphabet, "length": a.length,
                   "trials": len(results), "seconds": round(time.time() - t0, 1),
                   "results": results, "divergent": divergent}, fh, indent=2)
    print("saved -> %s   (%.0f min)" % (os.path.normpath(a.out), (time.time() - t0) / 60.0))
    return 1 if divergent else 0


if __name__ == "__main__":
    # Refuse to run if another rig job holds the lock. See harness/runlock.py.
    try:
        with runlock.exclusive("search"):
            sys.exit(main())
    except runlock.RigBusy as e:
        print("REFUSING TO START.")
        print(e)
        sys.exit(2)
