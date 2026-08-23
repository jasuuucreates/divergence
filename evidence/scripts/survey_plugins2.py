#!/usr/bin/env python
"""
Does the harness generalise, or did we find one bug in one plugin?

v2: probes raw.githubusercontent.com directly. The GitHub REST API rate-limits
unauthenticated callers at 60/hour and v1 stalled on it; raw has no such limit.

Reads the REAL webhook source of every public Razorpay e-commerce plugin and tests for
the same defect classes we proved by execution in razorpay-woocommerce:

  D1  a webhook handler exists at all
  D2  a guard that SILENTLY DROPS an event when the order looks unpaid   (the F4 mechanism)
  D3  deferred / queued processing that can invert event order            (the F4 precondition)
  D4  server-side verification of the AMOUNT actually paid
  D5  duplicate suppression keyed on x-razorpay-event-id                  (Razorpay's own advice)
"""
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# (repo, branch, [candidate webhook source paths])
TARGETS = [
    ("razorpay-woocommerce", "master", ["includes/razorpay-webhook.php"]),
    ("razorpay-magento", "master-2.x", ["Controller/Payment/Webhook.php"]),
    ("razorpay-prestashop", "master", ["webhook.php", "controllers/front/webhook.php",
                                       "razorpay/webhook.php", "controllers/front/validation.php"]),
    ("razorpay-opencart", "master", ["upload/catalog/controller/extension/payment/razorpay_webhook.php",
                                     "upload/catalog/controller/payment/razorpay_webhook.php",
                                     "catalog/controller/extension/payment/razorpay_webhook.php"]),
    ("razorpay-whmcs", "master", ["modules/gateways/razorpay/razorpay-webhook.php",
                                  "modules/gateways/callback/razorpay.php",
                                  "modules/gateways/razorpay.php"]),
    ("razorpay-edd", "master", ["includes/razorpay-webhook.php", "razorpay-edd.php"]),
    ("razorpay-cscart", "master", ["app/payments/razorpay_webhook.php", "app/payments/razorpay.php"]),
]

DROP_GUARDS = [
    r"needs_payment\(\)",
    r"already\s+(been\s+)?(paid|processed|refunded)",
    r"if\s*\([^)]{0,60}(is_paid|isPaid|hasInvoices|getState\(\))[^)]{0,60}\)\s*\{?\s*(return|exit)",
]
DEFER = [r"\bcron\b", r"wp_schedule_event", r"\bqueue\b", r"notified_at", r"deferred"]
AMOUNT = [r"amount\s*(!==|!=|===|==)\s*", r"get_total\(\)", r"getGrandTotal\(\)", r"grand_total"]
EVENTID = [r"x-razorpay-event-id", r"X_RAZORPAY_EVENT_ID", r"razorpay-event-id"]
SIGVERIFY = [r"verifyWebhookSignature", r"hash_hmac", r"hash_equals"]


def raw(repo, branch, path):
    url = "https://raw.githubusercontent.com/razorpay/%s/%s/%s" % (repo, branch, path)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "conformance-survey"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return url, r.read().decode("utf-8", "replace")
    except Exception:
        return url, None


print("=" * 112)
print("RAZORPAY PLUGIN SURVEY  --  do our defect classes generalise beyond WooCommerce?")
print("=" * 112)
print("%-24s %-6s %-10s %-9s %-9s %-9s %-8s" % ("PLUGIN", "HOOK", "DROPGUARD", "DEFERRED", "AMT-CHK", "EVENT-ID", "SIGVER"))
print("-" * 112)

rows = []
for repo, branch, paths in TARGETS:
    url, blob, found = None, None, None
    for p in paths:
        url, blob = raw(repo, branch, p)
        if blob:
            found = p
            break
    if not blob:
        print("%-24s %-6s  (no webhook source found at the probed paths)" % (repo, "?"))
        rows.append({"plugin": repo, "webhook_found": False, "probed": paths})
        continue

    hit = lambda pats: any(re.search(p, blob, re.I) for p in pats)
    r = {
        "plugin": repo, "webhook_found": True, "path": found, "bytes": len(blob),
        "drop_guard": hit(DROP_GUARDS), "deferred": hit(DEFER),
        "verifies_amount": hit(AMOUNT), "event_id_dedup": hit(EVENTID),
        "verifies_signature": hit(SIGVERIFY),
    }
    rows.append(r)
    print("%-24s %-6s %-10s %-9s %-9s %-9s %-8s" % (
        repo, "yes",
        "YES" if r["drop_guard"] else "no",
        "YES" if r["deferred"] else "no",
        "yes" if r["verifies_amount"] else "** NO **",
        "yes" if r["event_id_dedup"] else "** NO **",
        "yes" if r["verifies_signature"] else "** NO **"))

print("-" * 112)
w = [r for r in rows if r.get("webhook_found")]
n = len(w)
if n:
    print("webhook handler found                     : %d of %d probed" % (n, len(rows)))
    print("has a SILENT DROP guard (F4 mechanism)    : %d of %d" % (sum(1 for r in w if r["drop_guard"]), n))
    print("has deferred/queued processing            : %d of %d" % (sum(1 for r in w if r["deferred"]), n))
    print("verifies the AMOUNT paid                  : %d of %d" % (sum(1 for r in w if r["verifies_amount"]), n))
    print("suppresses duplicates via event id        : %d of %d" % (sum(1 for r in w if r["event_id_dedup"]), n))
    print("verifies the signature                    : %d of %d" % (sum(1 for r in w if r["verifies_signature"]), n))

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin_survey.json")
io.open(out, "w", encoding="utf-8").write(json.dumps(rows, indent=2))
print("\nsaved -> experiments/plugin_survey.json")
