#!/usr/bin/env python
"""
Making the documentation executable -- stage 1: find the sentences that could be properties.

Razorpay publish every documentation page as markdown under /docs/build/llm-docs/, indexed from a
496 KB llms.txt. That is a machine-readable corpus of the contract a merchant is expected to honour.
Almost none of it is ever tested.

This stage is DELIBERATELY DETERMINISTIC AND DUMB. It fetches the corpus, splits it into sentences,
and keeps the ones carrying normative force -- must / should / always / never / expected / cannot /
may not / ensure. No model is involved. The output is a candidate list, not a specification.

Why it matters that this stage has no model in it: everything downstream is judged against sentences
that provably exist in the corpus, byte for byte. When a later stage claims a property is grounded in
"Razorpay says X", that claim is checkable against a file on disk that was fetched, hashed and dated
-- which is exactly the check I failed personally when I once wrote a citation myself and presented
it as a quotation (see INCIDENTS.md, 2026-08-23).

    python harness/specmine.py --fetch      # download the corpus (writes spec/corpus/)
    python harness/specmine.py              # extract candidates from what is already downloaded
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORPUS = os.path.join(ROOT, "spec", "corpus")
INDEX = os.path.join(ROOT, "spec", "corpus_index.json")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LLMS_TXT = "https://razorpay.com/docs/llms.txt"

# Pages whose subject matter our rig can actually exercise. Fetching the whole 496 KB index would
# produce candidates about features we cannot test, and a candidate we can never decide is noise.
WANTED = re.compile(r"llm-docs/(webhooks|payments/(refunds|orders|capture-settle|"
                    r"payment-methods|recurring-payments|smart-collect)|api/orders)", re.I)

# A sentence carries normative force if it constrains an implementation. These are the modal verbs
# and phrasings that do that in practice; anything else is description.
NORMATIVE = re.compile(
    r"\b(must|must not|should|should not|shall|always|never|cannot|can not|"
    r"may not|is expected|are expected|expected behaviour|expected behavior|"
    r"ensure that|make sure|do not|don't|required to|is not guaranteed|not fixed)\b", re.I)

# Sentences that LOOK normative but constrain the reader's UI journey, not their integration.
NOT_A_PROPERTY = re.compile(
    r"\b(click|navigate|dashboard|log in|sign up|select the|go to|scroll|"
    r"contact (us|support)|refer to|see the|watch|screenshot|menu|button)\b", re.I)


def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": "divergence-specmine"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def do_fetch():
    os.makedirs(CORPUS, exist_ok=True)
    print("index : %s" % LLMS_TXT)
    idx = fetch(LLMS_TXT)
    urls = sorted(set(re.findall(r"https://razorpay\.com/docs/build/llm-docs/[^\s)\"']+\.md", idx)))
    wanted = [u for u in urls if WANTED.search(u)]
    print("  %d markdown pages listed, %d match the surface our rig can exercise\n" % (len(urls), len(wanted)))

    records = []
    for u in wanted:
        name = re.sub(r"[^a-z0-9]+", "_", u.split("llm-docs/")[1].replace(".md", "").lower()) + ".md"
        try:
            body = fetch(u)
        except Exception as e:
            print("  FAIL %-58s %s" % (name, str(e)[:40]))
            continue
        path = os.path.join(CORPUS, name)
        io.open(path, "w", encoding="utf-8", newline="\n").write(body)
        rec = {"url": u, "file": name, "bytes": len(body),
               "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()}
        records.append(rec)
        print("  ok   %-58s %6d B  %s" % (name, len(body), rec["sha256"][:12]))

    io.open(INDEX, "w", encoding="utf-8").write(json.dumps(
        {"source": LLMS_TXT, "pages": records}, indent=2))
    print("\n%d pages -> %s" % (len(records), os.path.relpath(CORPUS, ROOT)))
    print("index (url, sha256, size) -> %s" % os.path.relpath(INDEX, ROOT))


def sentences(text):
    """Split markdown into sentences, dropping code, tables and headings.

    Code blocks are dropped because a line inside a fence is an example, not an obligation, and
    including them produced candidates like 'do not skip payment verification' lifted out of a
    comment -- true, but not a sentence anyone can be held to.
    """
    text = re.sub(r"(?s)```.*?```", " ", text)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"(?m)^\s*\|.*$", " ", text)          # tables
    text = re.sub(r"(?m)^\s*#{1,6}\s.*$", " ", text)    # headings
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links -> their text
    text = re.sub(r"\s+", " ", text)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def extract():
    if not os.path.isdir(CORPUS):
        raise SystemExit("no corpus. Run:  python harness/specmine.py --fetch")
    idx = json.load(io.open(INDEX, encoding="utf-8")) if os.path.exists(INDEX) else {"pages": []}
    by_file = {p["file"]: p for p in idx.get("pages", [])}

    cands, seen, stats = [], set(), {"sentences": 0, "normative": 0, "ui": 0, "dupe": 0, "short": 0}
    for fn in sorted(os.listdir(CORPUS)):
        if not fn.endswith(".md"):
            continue
        body = io.open(os.path.join(CORPUS, fn), encoding="utf-8").read()
        for s in sentences(body):
            stats["sentences"] += 1
            if not NORMATIVE.search(s):
                continue
            stats["normative"] += 1
            if NOT_A_PROPERTY.search(s):
                stats["ui"] += 1
                continue
            if len(s) < 40 or len(s) > 400:
                stats["short"] += 1
                continue
            key = re.sub(r"\W+", "", s.lower())[:120]
            if key in seen:
                stats["dupe"] += 1
                continue
            seen.add(key)
            cands.append({"sentence": s, "file": fn,
                          "url": by_file.get(fn, {}).get("url"),
                          "sha256": by_file.get(fn, {}).get("sha256")})

    print("=" * 100)
    print("CANDIDATE NORMATIVE SENTENCES -- extracted deterministically, no model involved")
    print("=" * 100)
    print("  sentences scanned      : %d" % stats["sentences"])
    print("  carry normative force  : %d" % stats["normative"])
    print("  dropped, UI/navigation : %d" % stats["ui"])
    print("  dropped, length bounds : %d" % stats["short"])
    print("  dropped, duplicates    : %d" % stats["dupe"])
    print("  CANDIDATES             : %d\n" % len(cands))

    for c in cands[:25]:
        print("  [%s]" % c["file"][:34])
        print("    %s\n" % c["sentence"][:250])
    if len(cands) > 25:
        print("  ... %d more" % (len(cands) - 25))

    out = os.path.join(ROOT, "spec", "candidates.json")
    io.open(out, "w", encoding="utf-8").write(json.dumps(
        {"stats": stats, "candidates": cands}, indent=2))
    print("\nsaved -> %s" % os.path.relpath(out, ROOT))
    return cands


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="download the corpus first")
    a = ap.parse_args()
    os.makedirs(os.path.join(ROOT, "spec"), exist_ok=True)
    if a.fetch:
        do_fetch()
        print()
    extract()
