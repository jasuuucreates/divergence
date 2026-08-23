"""
The property checker.

Takes an event multiset, explores the delivery schedules the vendor says are legal, and decides each
contract property by comparing observed terminal states. The oracle is comparison against a
contract-derived expectation -- never a model's opinion, and never "did anything crash".

Verdict vocabulary is Razorpay's own (ai-playbook, GREEN/YELLOW/RED), used the way their playbook
says to use it: "The colour is not a judgement. It is a routing decision."
  GREEN  - the property held across every schedule explored
  YELLOW - could not be decided from outside (state not observable, or the property is structural)
  RED    - a counterexample exists, and it is printed

Usage:
    python harness/check.py                     # default multiset
    python harness/check.py --events payment.authorized refund.created
    python harness/check.py --dry-run           # print the plan without touching the rig
"""
import argparse
import itertools
import subprocess
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contract  # noqa: E402
import rig       # noqa: E402
import measured  # noqa: E402
import runlock   # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def schedules(events):
    """Every distinct ordering of the multiset. Razorpay: 'you may not always receive the webhooks
    in the order' -- so each of these is an input the integration is told to expect."""
    return sorted(set(itertools.permutations(events)))


def check_order_independence(events, dry=False):
    """P1. All legal orderings must converge to the same terminal state."""
    plans = schedules(events)
    if dry:
        return {"property": contract.ORDER_INDEPENDENCE.key, "verdict": "DRY",
                "schedules_planned": [list(p) for p in plans]}
    trials = []
    for p in plans:
        t = rig.trial(list(p))
        trials.append(t)
        print("    %-46s -> %s" % (" then ".join(p), t["terminal"]["order_status"]))
    # A verdict requires evidence. Without this, all-None terminal states collapse to a set of
    # size one and this line returns GREEN having measured nothing. See harness/measured.py.
    measured.require(trials, "order_status")
    states = {t["terminal"]["order_status"] for t in trials}
    verdict = "GREEN" if len(states) == 1 else "RED"
    out = {"property": contract.ORDER_INDEPENDENCE.key, "verdict": verdict,
           "distinct_terminal_states": sorted(x for x in states if x), "trials": trials}
    if verdict == "RED":
        # minimal witness = the two schedules that disagree, nothing more
        by_state = {}
        for t in trials:
            by_state.setdefault(t["terminal"]["order_status"], t)
        out["witness"] = [{"schedule": t["sequence"], "terminal": t["terminal"]["order_status"],
                           "order": t["order"]} for t in by_state.values()]
    return out


def check_duplicate_tolerance(events, dry=False):
    """P2. Redelivering an event must not change the terminal state."""
    base = list(events)
    dup = list(events) + [events[-1]]   # redeliver the LAST event, not the first
    if dry:
        return {"property": contract.DUPLICATE_TOLERANCE.key, "verdict": "DRY",
                "baseline": base, "with_duplicate": dup}
    a = rig.trial(base)
    b = rig.trial(dup)
    measured.require([a, b], "order_status")

    # Compare the FULL merchant-visible state, not just the order status. Status is identical
    # whether an order was refunded once or twice, so a status-only comparison is blind to
    # double-refunding by construction -- which is exactly why this property was vacuous until
    # harness/vacuity.py caught it. See rig.terminal_state().
    def visible(t):
        return {k: t["terminal"].get(k) for k in ("order_status", "refund_count", "refunded_total")}

    va, vb = visible(a), visible(b)
    print("    %-30s -> %s" % ("baseline", va))
    print("    %-30s -> %s" % ("redelivered", vb))
    same = va == vb
    if not same:
        differing = [k for k in va if va[k] != vb[k]]
        print("    !! redelivery changed: %s" % ", ".join(differing))
    return {"property": contract.DUPLICATE_TOLERANCE.key,
            "verdict": "GREEN" if same else "RED",
            "baseline": a, "with_duplicate": b,
            "witness": None if same else {"baseline": va, "with_duplicate": vb}}


def check_no_silent_loss(events, dry=False):
    """P4. An event answered 2xx must change the state or be durably recorded.

    Run UNDER AN INDUCED UPSTREAM FAILURE. On the happy path the integration moves the order and the
    property is trivially satisfied, so a clean run proves nothing. The interesting question is what
    the integration does when its own dependency fails: does it retry, or does it acknowledge the
    money event and drop it? Razorpay retries only what was not acknowledged, so an endpoint that
    answers 2xx and then does nothing has silently consumed a payment."""
    if dry:
        return {"property": contract.NO_SILENT_LOSS.key, "verdict": "DRY", "sequence": list(events),
                "note": "runs with fault injection: upstream payment fetch returns 500"}
    t = rig.trial(list(events), fault=True)
    measured.require([t], "queue_cron_status")
    accepted = [d["event"] for d in t["deliveries"] if str(d["http"]).startswith("2")]
    stored = t["terminal"]["stored_events"] or []
    # An event is "accounted for" if it is durably recorded, or if it visibly moved the order.
    unaccounted = [e for e in accepted if e not in stored]
    moved = t["terminal"]["order_status"] not in (None, "wc-pending")
    consumed = t["terminal"]["queue_cron_status"] == "2"
    # The failure we are hunting: the queue row was marked CONSUMED while the order never moved.
    # Razorpay's own playbook, B09: "A confident 'done' is not evidence that the state changed."
    silently_lost = consumed and not moved
    verdict = "RED" if silently_lost else ("GREEN" if (not unaccounted or moved) else "RED")
    print("    accepted=%s  stored=%s  terminal=%s  queue=%s"
          % (accepted, stored, t["terminal"]["order_status"], t["terminal"]["queue_cron_status"]))
    if silently_lost:
        print("    !! queue row marked consumed (cron_status=2) while the order never left pending")
        print("    !! the drain re-selects only cron_status=0, so this event is never retried")
    return {"property": contract.NO_SILENT_LOSS.key, "verdict": verdict,
            "accepted": accepted, "durably_recorded": stored, "unaccounted": unaccounted,
            "queue_marked_consumed": consumed, "order_moved": moved,
            "silently_lost": silently_lost, "trial": t}


def check_amount_integrity(events, dry=False):
    """P5. An order must not reach a paid state for an amount other than the amount ordered.

    Delivered via a payment id the stub answers with a deliberately mismatched amount, so the
    mismatch is visible in the transcript rather than hidden in configuration. See
    harness/amount_integrity.py for the standalone version and its scope caveat: this shows the
    integration does not DEFEND the invariant, not that an attacker can choose the amount."""
    if dry:
        return {"property": contract.AMOUNT_INTEGRITY.key, "verdict": "DRY",
                "note": "delivers an authorized payment for 100 paise against the order total"}
    t = rig.trial(["payment.authorized"], underpay=True)
    measured.require([t], "order_status")
    st = t["terminal"]["order_status"]
    paid = st in ("wc-processing", "wc-completed")
    print("    order total vs amount paid mismatched -> terminal=%s" % st)
    if paid:
        print("    !! order reached a paid state despite the amount not matching")
    return {"property": contract.AMOUNT_INTEGRITY.key,
            "verdict": "RED" if paid else "GREEN", "trial": t}


def preflight():
    """Refuse to run against a rig that cannot produce a meaningful answer.

    Without the stub, paymentAuthorized()'s payment fetch goes to the real api.razorpay.com with
    synthetic credentials, 401s, and every order stays `pending`. The harness would then report
    confident verdicts derived from an integration that never did anything -- which is worse than
    an error, because it looks like a result.

    This is the same failure shape as the false-negative CONVERGENT run recorded in INCIDENTS.md:
    the control arm must be known-good before the treatment arm is believed.
    """
    probe = subprocess.run(
        ["docker", "compose", "exec", "-T", "wordpress", "sh", "-c",
         "curl -s -o /dev/null -w '%{http_code}' http://rzpstub:8000/v1/payments/pay_RIG00000000001"],
        cwd=rig.RIG, env=rig._env(), capture_output=True, text=True, timeout=120)
    if (probe.stdout or "").strip() != "200":
        raise SystemExit(
            "REFUSING TO RUN: the API stub is not reachable from the WordPress container.\n"
            "  Without it every order stays `pending` and the verdicts would be meaningless.\n"
            "  Fix:  cd rig && ./setup.sh          (the stub is on by default)\n"
            "  Got:  %r from http://rzpstub:8000" % (probe.stdout or probe.stderr or "")[:120])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", nargs="+",
                    default=["payment.authorized", "refund.created"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "..", "rig", "out", "conformance_report.json"))
    a = ap.parse_args()

    print("=" * 96)
    print("CONFORMANCE RUN -- razorpay-woocommerce")
    print("=" * 96)
    if not a.dry_run:
        preflight()
    print("events under test : %s" % " + ".join(a.events))
    print("legal schedules   : %d (vendor states delivery order is not guaranteed)"
          % len(schedules(a.events)))
    print()

    results = []
    for name, fn in (("P1 order independence", check_order_independence),
                     ("P2 duplicate tolerance", check_duplicate_tolerance),
                     ("P4 no silent loss", check_no_silent_loss),
                     ("P5 amount integrity", check_amount_integrity)):
        print("  %s" % name)
        t0 = time.time()
        try:
            r = fn(a.events, dry=a.dry_run)
        except measured.NotMeasured as e:
            r = {"property": name, "verdict": "UNMEASURED", "why": str(e)}
            print("    !! %s" % str(e).splitlines()[0])
        r["seconds"] = round(time.time() - t0, 1)
        results.append(r)
        print("    -> %s  (%ss)\n" % (r["verdict"], r["seconds"]))

    # P3 is structural: reported as advisory, never as a failure. See contract.py.
    results.append({"property": contract.EVENT_ID_DEDUP.key, "verdict": "YELLOW",
                    "note": "structural check -- see experiments/eventid_survey.json; "
                            "absence of the header proves the prescribed mechanism is absent, "
                            "not that the integration is non-idempotent. P2 decides idempotence."})

    reds = [r for r in results if r["verdict"] == "RED"]
    unmeasured = [r for r in results if r["verdict"] == "UNMEASURED"]
    # UNMEASURED outranks everything. A run that could not observe the integration has not
    # cleared it and has not condemned it, and must not be summarised as either.
    if unmeasured:
        overall = "UNMEASURED"
    else:
        overall = "RED" if reds else ("YELLOW" if any(r["verdict"] == "YELLOW" for r in results) else "GREEN")

    print("=" * 96)
    print("OVERALL: %s   (strict worst-case aggregation -- one RED makes the run RED)" % overall)
    for r in results:
        print("  %-24s %s" % (r["property"], r["verdict"]))
    print("=" * 96)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"overall": overall, "events": a.events,
                   "contract": contract.citations(), "results": results}, fh, indent=2)
    print("report -> %s" % os.path.normpath(a.out))
    return 1 if reds else 0


if __name__ == "__main__":
    # Refuse to run if another rig job holds the lock. See harness/runlock.py.
    try:
        with runlock.exclusive("check"):
            sys.exit(main())
    except runlock.RigBusy as e:
        print("REFUSING TO START.")
        print(e)
        sys.exit(2)
