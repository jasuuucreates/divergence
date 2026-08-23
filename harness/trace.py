#!/usr/bin/env python
"""
What did the integration actually DO?

Every verdict this harness produces is about merchant-visible state. The next question a reviewer
asks is fair and hard: "how do you know it dropped the refund, rather than recording it somewhere
you are not looking?"

The honest answer is a trace. rig/php/mu-rig-trace.php hooks WordPress's single query filter
(wp-includes/class-wpdb.php:2234) and records every statement a webhook delivery issues, without
touching the plugin under test. This reads that back.

The interesting output is usually an ABSENCE, and an absence is only convincing inside a complete
record. "It never wrote a refund row" means nothing on its own; "here are all 99 statements this
delivery issued, and none of them is an insert into the refund table" is evidence.

    python harness/trace.py --compare      # the two orderings, side by side, by what they DID
    python harness/trace.py --last         # every statement from the most recent delivery
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

sys.path.insert(0, HERE)
import measured  # noqa: E402
import rig       # noqa: E402
import runlock   # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# The statements that mean money moved, as opposed to the hundreds that mean WordPress was awake.
MATERIAL = [
    ("refund created", "INSERT", "wp_posts", "shop_order_refund"),
    ("order status written", "UPDATE", "wp_posts", None),
    ("webhook row written", "UPDATE", "wp_rzp_webhook_requests", None),
    ("order meta written", "INSERT", "wp_postmeta", None),
]


def clear():
    rig.sql("TRUNCATE TABLE wp_rig_query_trace;")


def summarise(label):
    """A delivery's statements, split into the ones that could move money and the rest."""
    total = rig.sql("SELECT COUNT(*) FROM wp_rig_query_trace;").strip()
    writes = rig.sql(
        "SELECT verb, tbl, COUNT(*) FROM wp_rig_query_trace "
        "WHERE verb IN ('INSERT','UPDATE','DELETE','REPLACE') "
        "GROUP BY verb, tbl ORDER BY 3 DESC;")
    refunds = rig.sql(
        "SELECT COUNT(*) FROM wp_rig_query_trace "
        "WHERE verb='INSERT' AND sql_text LIKE '%shop_order_refund%';").strip()
    print("\n  %s" % label)
    print("    statements issued : %s   (writes below; the rest are reads and WordPress overhead)" % total)
    for line in (writes or "").splitlines():
        if line.strip():
            v, t, n = (line.split("\t") + ["", "", ""])[:3]
            print("      %-8s %-30s %s" % (v, t, n))
    print("    refund rows inserted : %s" % (refunds or "0"))
    return {"total": total, "refund_inserts": int(refunds or 0)}


def compare():
    print("=" * 84)
    print("WHAT THE PLUGIN ACTUALLY DID -- the same events, the two legal orders")
    print("=" * 84)
    print("  Not what state it ended in. Every database statement it issued.")

    out = {}
    for label, seq in (("A: authorization settles first", ["payment.authorized", "refund.created"]),
                       ("B: refund arrives first", ["refund.created", "payment.authorized"])):
        clear()
        t = rig.trial(list(seq))
        measured.require([t], "order_status")
        s = summarise("%s   ->  %s" % (label, t["terminal"]["order_status"]))
        s["order"] = t["order"]
        out[label] = s

    a, b = list(out.values())
    print("\n" + "=" * 84)
    if a["refund_inserts"] and not b["refund_inserts"]:
        print("  Ordering A inserted %d refund row(s). Ordering B inserted %d."
              % (a["refund_inserts"], b["refund_inserts"]))
        print()
        print("  That is the finding stated as an action rather than as a state: in B the plugin")
        print("  never wrote a refund at all. It is not recorded elsewhere, not deferred, not")
        print("  pending -- across every statement that delivery issued, there is no refund.")
    elif a["refund_inserts"] == b["refund_inserts"]:
        print("  Both orderings inserted %d refund row(s). No difference in what the plugin DID,"
              % a["refund_inserts"])
        print("  which would contradict the state-level result. Investigate before claiming either.")
    else:
        print("  Unexpected: A=%d refund inserts, B=%d." % (a["refund_inserts"], b["refund_inserts"]))
    print("=" * 84)
    return 0


def last():
    print("=" * 84)
    print("EVERY STATEMENT FROM THE MOST RECENT DELIVERY")
    print("=" * 84)
    rows = rig.sql(
        "SELECT verb, tbl, LEFT(sql_text, 88) FROM wp_rig_query_trace "
        "WHERE req = (SELECT req FROM wp_rig_query_trace ORDER BY id DESC LIMIT 1) "
        "ORDER BY id;")
    n = 0
    for line in (rows or "").splitlines():
        if not line.strip():
            continue
        n += 1
        v, t, q = (line.split("\t") + ["", "", ""])[:3]
        print("  %-8s %-28s %s" % (v, t, q[:70]))
    print("\n  %d statements" % n)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--last", action="store_true")
    a = ap.parse_args()
    if a.last:
        sys.exit(last())
    try:
        with runlock.exclusive("trace"):
            sys.exit(compare())
    except runlock.RigBusy as e:
        print("REFUSING TO START.")
        print(e)
        sys.exit(2)
