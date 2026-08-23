#!/usr/bin/env python
"""
Does the harness generalise, or did we find one bug in one plugin?

Surveys every public Razorpay e-commerce plugin for the SAME defect classes we proved by
execution in razorpay-woocommerce. Reads real source from raw.githubusercontent.com --
no marketing pages, no inference from README.

Defect classes under test:
  D1  webhook handler exists at all
  D2  a guard that silently DROPS an event when the order looks unpaid  (the F4 mechanism)
  D3  deferred/queued processing that can invert event order            (the F4 precondition)
  D4  server-side verification of the AMOUNT actually paid
  D5  duplicate/replay suppression keyed on the event id                (x-razorpay-event-id)
"""
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PLUGINS = [
    ("razorpay-woocommerce", "master"),
    ("razorpay-magento", "master-2.x"),
    ("razorpay-prestashop", "master"),
    ("razorpay-opencart", "master"),
    ("razorpay-whmcs", "master"),
    ("razorpay-edd", "master"),
    ("razorpay-cscart", "master"),
]

UA = {"User-Agent": "Mozilla/5.0 conformance-survey"}


def get(url, timeout=45):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None


def tree(repo, branch):
    j = get("https://api.github.com/repos/razorpay/%s/git/trees/%s?recursive=1" % (repo, branch))
    if not j:
        return []
    try:
        return [t["path"] for t in json.loads(j).get("tree", []) if t.get("type") == "blob"]
    except Exception:
        return []


# Patterns. Each is (label, regex). Kept deliberately narrow so a hit means something.
DROP_GUARDS = [
    r"needs_payment\(\)\s*===?\s*true",          # woocommerce
    r"needs_payment\(\)\s*\)",
    r"if\s*\(\s*\$?order[^)]{0,40}(paid|pending|status)[^)]{0,40}\)\s*\{?\s*return\s*;",
]
DEFER = [r"cron", r"queue", r"schedule", r"deferred", r"wp_schedule_event"]
AMOUNT = [r"amount\s*(!=|!==|==|===)", r"get_total\(\)\s*[!=]=", r"getGrandTotal\(\)\s*[!=]="]
EVENTID = [r"x-razorpay-event-id", r"x_razorpay_event_id", r"HTTP_X_RAZORPAY_EVENT_ID", r"event_id"]

print("=" * 108)
print("RAZORPAY PLUGIN SURVEY -- do our defect classes generalise?")
print("=" * 108)
print("%-24s %-7s %-9s %-9s %-9s %-9s  %s" % ("PLUGIN", "WEBHK", "DROPGUARD", "DEFERRED", "AMT-CHK", "EVENT-ID", "webhook file"))
print("-" * 108)

rows = []
for repo, branch in PLUGINS:
    paths = tree(repo, branch)
    hooks = [p for p in paths if re.search(r"webhook", p, re.I) and re.search(r"\.(php|js|py|tpl)$", p, re.I)]
    if not hooks:
        print("%-24s %-7s %s" % (repo, "NO", "-- no webhook source file found --"))
        rows.append({"plugin": repo, "webhook": False})
        continue

    # biggest webhook file is the handler
    best, blob = None, ""
    for h in hooks:
        c = get("https://raw.githubusercontent.com/razorpay/%s/%s/%s" % (repo, branch, h))
        if c and len(c) > len(blob):
            best, blob = h, c
    if not blob:
        print("%-24s %-7s %s" % (repo, "?", "(could not fetch)"))
        continue

    hit = lambda pats: any(re.search(p, blob, re.I) for p in pats)
    d2, d3, d4, d5 = hit(DROP_GUARDS), hit(DEFER), hit(AMOUNT), hit(EVENTID)
    print("%-24s %-7s %-9s %-9s %-9s %-9s  %s"
          % (repo, "yes",
             "YES" if d2 else "no",
             "YES" if d3 else "no",
             "yes" if d4 else "** NO **",
             "yes" if d5 else "** NO **",
             (best or "")[:40]))
    rows.append({"plugin": repo, "webhook": True, "file": best, "bytes": len(blob),
                 "drop_guard": d2, "deferred": d3, "verifies_amount": d4, "event_id_dedup": d5})

print("-" * 108)
w = [r for r in rows if r.get("webhook")]
print("plugins with a webhook handler        : %d of %d" % (len(w), len(rows)))
print("with a silent DROP guard              : %d" % sum(1 for r in w if r.get("drop_guard")))
print("with deferred/queued processing       : %d" % sum(1 for r in w if r.get("deferred")))
print("that verify the AMOUNT paid           : %d of %d" % (sum(1 for r in w if r.get("verifies_amount")), len(w)))
print("with event-id duplicate suppression   : %d of %d" % (sum(1 for r in w if r.get("event_id_dedup")), len(w)))

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin_survey.json")
io.open(out, "w", encoding="utf-8").write(json.dumps(rows, indent=2))
print("\nsaved -> experiments/plugin_survey.json")
