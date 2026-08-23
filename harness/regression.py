#!/usr/bin/env python
"""
When did this defect appear?

"There is a bug" is a report. "This has been in every release since v3.0.0, shipped 2019" is
something a maintainer can triage, and something a reviewer can check without trusting us. OSS-Fuzz
ships a regression range with every crash for exactly this reason: the range tells you whether you
are looking at a fresh mistake or a long-standing assumption.

The method here is deliberately two-stage, because a purely static answer would be the weak kind of
evidence this project keeps arguing against:

  STAGE 1  screen every tagged release with a cheap static predicate, to find the BOUNDARY
  STAGE 2  confirm that boundary BEHAVIOURALLY, by standing the rig up on the two adjacent
           versions and running the property

Stage 1 alone would be a grep with a date attached. Stage 2 is what makes the range a claim about
behaviour rather than about text. If stage 2 disagrees with stage 1, stage 1 is wrong and the
disagreement is the finding.

    python harness/regression.py --screen        # stage 1 only, no Docker needed
    python harness/regression.py --confirm       # stage 2 at the boundary (slow, uses the rig)
"""
import argparse
import io
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "spec", "versions")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = "razorpay/razorpay-woocommerce"
FILE = "includes/razorpay-webhook.php"


def get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": "divergence-regression"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None


def tags():
    """Every tagged release, newest first, with its commit sha."""
    out, page = [], 1
    while page <= 3:
        j = get("https://api.github.com/repos/%s/tags?per_page=100&page=%d" % (REPO, page))
        if not j:
            break
        try:
            batch = json.loads(j)
        except Exception:
            break
        if not batch:
            break
        out += [(t["name"], t["commit"]["sha"]) for t in batch]
        if len(batch) < 100:
            break
        page += 1
    return out


def source_at(tag):
    """The webhook handler as it shipped in that release. Cached, so a re-run costs nothing."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9._-]", "_", tag) + ".php")
    if os.path.exists(path):
        return io.open(path, encoding="utf-8").read()
    body = get("https://raw.githubusercontent.com/%s/%s/%s" % (REPO, tag, FILE))
    if body is None:
        return None
    io.open(path, "w", encoding="utf-8", newline="\n").write(body)
    return body


def payment_authorized_body(src):
    """Isolate paymentAuthorized(). The defect is scoped to that function -- the same file DOES
    compare the amount on the virtual-account path, so a whole-file grep would wrongly clear it."""
    m = re.search(r"(?s)function\s+paymentAuthorized\s*\([^)]*\)\s*\{(.*?)\n    \}", src)
    return m.group(1) if m else None


def defect_present(src):
    """Static predicate for C6: does paymentAuthorized() compare paid against ordered?

    Returns (present, why). `present` is True when the comparison is ABSENT, i.e. the defect is
    there. None means undecidable for this version, which is reported rather than guessed.
    """
    body = payment_authorized_body(src)
    if body is None:
        return None, "paymentAuthorized() not found in this version"
    computes = bool(re.search(r"\$amount\s*=\s*\$this->getOrderAmountAsInteger", body))
    if not computes:
        return None, "does not compute an expected amount here at all"
    # Any comparison that puts the payment amount against the order amount, in either order.
    compares = re.search(
        r"""\$payment\s*\[\s*['"]amount['"]\s*\]\s*[!=]==?\s*.{0,30}\$amount"""
        r"""|\$amount\s*[!=]==?\s*.{0,30}\$payment\s*\[\s*['"]amount['"]\s*\]""", body)
    if compares:
        return False, "compares: %s" % compares.group(0).strip()[:60]
    return True, "computes $amount but never compares it to the amount paid"


def screen():
    ts = tags()
    print("=" * 96)
    print("REGRESSION SCREEN -- C6 (paymentAuthorized never compares paid against ordered)")
    print("=" * 96)
    print("%d tagged releases of %s\n" % (len(ts), REPO))

    rows = []
    for name, sha in ts:
        src = source_at(name)
        if src is None:
            rows.append({"tag": name, "sha": sha[:10], "present": None, "why": "file absent"})
            continue
        present, why = defect_present(src)
        rows.append({"tag": name, "sha": sha[:10], "present": present, "why": why})

    known = [r for r in rows if r["present"] is not None]
    with_defect = [r for r in known if r["present"]]
    without = [r for r in known if not r["present"]]

    print("  releases screened      : %d" % len(rows))
    print("  decidable              : %d" % len(known))
    print("  defect PRESENT         : %d" % len(with_defect))
    print("  defect ABSENT          : %d" % len(without))
    print("  undecidable            : %d\n" % (len(rows) - len(known)))

    # Tags come newest-first. A boundary is a place where consecutive decidable releases disagree.
    boundaries = []
    for a, b in zip(known, known[1:]):
        if a["present"] != b["present"]:
            boundaries.append((b, a))   # (older, newer)

    if not with_defect:
        print("  The defect is not present in any screened release. Re-check the predicate.")
    elif not without:
        oldest = known[-1]
        print("  NO BOUNDARY FOUND: the defect is present in every decidable release screened,")
        print("  back to and including %s (%s)." % (oldest["tag"], oldest["sha"]))
        print("  This is not a regression. It is an original characteristic of the code.")
    else:
        for older, newer in boundaries:
            print("  BOUNDARY: %s (%s) -> %s (%s)" % (older["tag"], "present" if older["present"] else "absent",
                                                      newer["tag"], "present" if newer["present"] else "absent"))

    print("\n  %-14s %-10s %s" % ("TAG", "DEFECT", "BASIS"))
    for r in rows[:8] + ([{"tag": "...", "sha": "", "present": None, "why": ""}] if len(rows) > 16 else []) + rows[-8:]:
        mark = "-" if r["present"] is None else ("PRESENT" if r["present"] else "absent")
        print("  %-14s %-10s %s" % (r["tag"], mark, (r["why"] or "")[:58]))

    out = os.path.join(ROOT, "spec", "regression.json")
    io.open(out, "w", encoding="utf-8").write(json.dumps(
        {"repo": REPO, "file": FILE, "screened": len(rows), "rows": rows,
         "boundaries": [{"older": o["tag"], "newer": n["tag"]} for o, n in boundaries]}, indent=2))
    print("\n  STATIC ONLY. A grep with a date attached is the weak form of this evidence.")
    print("  Run --confirm to check the boundary (or the oldest release) behaviourally.")
    print("saved -> %s" % os.path.relpath(out, ROOT))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--screen", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    a = ap.parse_args()
    if a.confirm:
        print("Behavioural confirmation is run by harness/confirm_range.py -- see that file.")
    screen()
