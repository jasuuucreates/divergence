#!/usr/bin/env python
"""
ONE claim, checked properly.

Two earlier survey passes (survey_plugins.py, survey_plugins2.py) DISAGREED with each other on
which plugins verify the amount -- different probed paths and over-loose regexes. That makes those
results unpublishable. This script drops every semantic pattern-match and tests a single thing that
grep can actually decide:

  Does the plugin's webhook handler reference Razorpay's own duplicate-suppression header,
  `x-razorpay-event-id`, at all?

This is an ABSENCE check on a literal string. There is no interpretation, no false-positive class,
and it is trivially reproducible by anyone with curl and grep.

Razorpay's own webhook documentation tells integrators to use that header to de-duplicate, because
delivery is at-least-once. If a plugin never mentions it, it cannot be de-duplicating on it.

Paths below are the REAL handler paths recovered by enumerating each repo's git tree (survey v1),
not guesses.
"""
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TARGETS = [
    ("razorpay-woocommerce", "master",     "includes/razorpay-webhook.php"),
    ("razorpay-magento",     "master-2.x", "Controller/Payment/Webhook.php"),
    ("razorpay-prestashop",  "master",     "razorpay/razorpay-webhook.php"),
    ("razorpay-whmcs",       "master",     "modules/gateways/razorpay/razorpay-webhook.php"),
    ("razorpay-edd",         "master",     "includes/razorpay-webhook.php"),
    ("razorpay-cscart",      "master",     "app/payments/razorpay/razorpay-webhook.php"),
]

# Literal spellings of the header across PHP superglobal / header-bag conventions.
EVENT_ID = [
    "x-razorpay-event-id",
    "X-Razorpay-Event-Id",
    "HTTP_X_RAZORPAY_EVENT_ID",
    "x_razorpay_event_id",
    "razorpay-event-id",
]


def raw(repo, branch, path):
    url = "https://raw.githubusercontent.com/razorpay/%s/%s/%s" % (repo, branch, path)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "conformance-survey"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return url, r.read().decode("utf-8", "replace")
    except Exception as e:
        return url, None


print("=" * 100)
print("Do Razorpay's own plugins de-duplicate on x-razorpay-event-id?")
print("=" * 100)
print("%-24s %-9s %-10s  %s" % ("PLUGIN", "FETCHED", "EVENT-ID", "handler"))
print("-" * 100)

rows, fetched = [], 0
for repo, branch, path in TARGETS:
    url, blob = raw(repo, branch, path)
    if blob is None:
        print("%-24s %-9s %-10s  %s" % (repo, "FAIL", "-", path))
        rows.append({"plugin": repo, "fetched": False, "url": url})
        continue
    fetched += 1
    hits = [e for e in EVENT_ID if re.search(re.escape(e), blob, re.I)]
    rows.append({"plugin": repo, "fetched": True, "url": url, "bytes": len(blob),
                 "event_id_refs": hits})
    print("%-24s %-9s %-10s  %s" % (repo, "%d B" % len(blob),
                                    (",".join(hits) if hits else "** ABSENT **"), path))

print("-" * 100)
absent = [r for r in rows if r.get("fetched") and not r["event_id_refs"]]
print("handlers fetched                       : %d of %d" % (fetched, len(TARGETS)))
print("that NEVER mention x-razorpay-event-id : %d of %d" % (len(absent), fetched))
print()
print("Reproduce any row in one line:")
print("  curl -s https://raw.githubusercontent.com/razorpay/<plugin>/<branch>/<path> | grep -ci event-id")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eventid_survey.json")
io.open(out, "w", encoding="utf-8").write(json.dumps(rows, indent=2))
print("\nsaved -> evidence/eventid_survey.json")
