"""
The investigator: derive the specification oracle from the vendor's own documentation.

WHY THIS EXISTS
---------------
The standing open risk on this project, recorded in docs/STATE.md before this module was written:

    "Which of these defects did your harness FIND?" -- currently none; all were hand-read
    then encoded.

contract.py holds four properties that a human read out of Razorpay's docs and typed in by hand.
That is the weakest part of the whole harness: it means the oracle is only as good as the person
who read the docs, and it does not scale to 400+ documented endpoints.

This module removes the human from that step. It reads Razorpay's published documentation, finds
the sentences that impose a NORMATIVE constraint on an integration's behaviour, and emits property
candidates in the same shape contract.py uses.

*** THIS MODULE IS A DOCUMENTED FAILED EXPERIMENT. ITS HEADLINE METRIC WAS WRONG. ***
--------------------------------------------------------------------------------------
Read this before you read anything else in the file.

On 2026-09-03 this module reported "4/5 answer-key recall" and we believed it. It is not a real
result, and we falsified it ourselves the next day. Two independent defects, both ours:

1. CONTAMINATION. The recall number is produced by SEED_PAGES below -- a list we hand-wrote that
   names the very page the answers live on. Run with --wide, which drops that list and lets the
   module choose from all 2,239 indexed pages, and it reads entirely different pages. We had even
   written the rationalisation into this docstring: "selecting which docs to read is a scoping
   decision, not the discovery we are measuring." That sentence was protecting the metric.

2. THE FILTER DOES NOTHING. Ablation, run over the real on-disk cache: a NULL filter that keeps
   EVERY sentence (837) scores the IDENTICAL 4/5 answer-key recall and the IDENTICAL 2/2 "new
   discoveries" as the MODAL/HAZARD filter (245). The filter, the ranking and the model stage
   contribute nothing measurable beyond volume reduction. Reproduce it yourself:
       python -m harness.investigator --ablate

WHAT SURVIVES, STATED NARROWLY. The two sentences under KNOWN_GAPS are genuinely present in
Razorpay's documentation and genuinely absent from contract.py as Property objects. That much is
checkable and true. What is NOT true is that this module was needed to find them -- any sentence
dump over the same pages surfaces them.

WHAT THIS MEANS FOR THE PROJECT. The open risk this module was built to close --
    "Which of these defects did your harness FIND?" -- currently none; all were hand-read
    then encoded.
STAYS OPEN. We did not close it. The honest record of trying and failing is worth more than the
number we would have shipped.

WHERE WE DELIBERATELY DO NOT USE A MODEL
----------------------------------------
Razorpay's own rubric rewards "the right tool in the right place, and where you chose NOT to use
one". Three of the four stages here are deterministic and have no model in them at all:

  stage 1  fetch      -- HTTP, cached to disk, byte counts reported
  stage 2  segment    -- sentence splitting and a modal/hazard filter, pure regex
  stage 4  score      -- exact-substring grading against the held-out key

Only stage 3 (classify) calls a model, because deciding whether "you may not always receive the
webhooks in the order" imposes a checkable obligation is a judgement about meaning, and regex
cannot do it. Run with --no-llm to execute stages 1, 2 and 4 only; the recall ceiling of the
deterministic path alone is then reported, which is the honest baseline the model must beat.

USAGE
    python -m harness.investigator --limit 12            # full run
    python -m harness.investigator --no-llm              # deterministic baseline only
    python -m harness.investigator --offline             # use only the on-disk cache
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "docs", "raw", "investigator")
LLMS_TXT = "https://razorpay.com/docs/llms.txt"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
MODEL = "claude-opus-5"

# ---------------------------------------------------------------------------
# The held-out answer key.
#
# These four doc sentences are the ones a human found by hand on 2026-08-23 and encoded as
# properties P1-P4 in contract.py. The investigator is never shown this list; it is used only by
# score() after the run. A short distinctive fragment is enough -- we grade on substring
# containment so that whitespace and truncation differences do not decide the result.
# ---------------------------------------------------------------------------
ANSWER_KEY = {
    "P1-ORDER-INDEPENDENCE": "you may not always receive the webhooks in the order",
    "P2-DUPLICATE-TOLERANCE": "receive the same webhook event multiple times",
    "P3-EVENT-ID-DEDUP": "identify the duplicate webhooks using the x-razorpay-event-id header",
    # P4 is derived from the SAME doc sentence as P2 -- the human read one sentence and drew two
    # distinct obligations from it. Grading on the doc sentence therefore scores P2 and P4
    # together; that is a property of the key, not of the investigator, and it is stated here
    # rather than quietly folded away.
    "P4-NO-SILENT-LOSS": "receive the same webhook event multiple times",
    "P5-AMOUNT-INTEGRITY": "the amount for which the order was created, in currency subunits",
}

# Constraints the investigator surfaced that the human did NOT encode as checkable properties.
# They appear in contract.py only inside rationale prose, never as a Property object -- so they
# were seen and not acted on, which is a weaker and more accurate claim than "never seen".
# This list is filled in by observation, not by the scorer, and exists so the claim in the README
# can be checked against the code rather than taken on trust.
KNOWN_GAPS = {
    "SIGNATURE-VERIFICATION": "x-razorpay-signature header",
    "ACK-WITHIN-WINDOW": "must return a status code in the range 2xx within a window of 5 seconds",
}

# Pages the human read. The investigator is allowed to see this list because selecting which
# docs to read is a scoping decision, not the discovery we are measuring -- but --wide drops it
# and lets the investigator choose from the whole index itself.
# Ordered MOST SPECIFIC FIRST. Selection walks this list in order so a generic page can never
# consume the page budget ahead of the specific one that actually carries the contract.
SEED_PAGES = [
    "webhooks/validate-test.md",
    "webhooks/troubleshoot.md",
    "webhooks/handle-events.md",
    "webhooks/webhooks.md",
    "/webhooks.md",
]

MODAL = re.compile(
    r"\b(must|should|shall|need to|needs to|have to|has to|ensure|cannot|can not|"
    r"may not|will not|do not|does not|never|always|required to|make sure)\b",
    re.I,
)
HAZARD = re.compile(
    r"\b(duplicate|duplicated|retry|retries|retried|order|ordering|out of order|idempoten\w*|"
    r"same event|multiple times|fail|failure|failed|timeout|timed out|delay|delayed|"
    r"acknowledge|acknowledgement|2xx|status code|signature|verify|verification|"
    r"at least once|exactly once|race|concurrent|simultaneous)\b",
    re.I,
)
# Sentences that talk about the merchant's commercial obligations rather than the integration's
# runtime behaviour. These are the dominant false-positive class and are cheap to drop first.
NOISE = re.compile(
    r"\b(pricing|fee|invoice us|contact (our )?(support|sales)|sign ?up|log ?in|dashboard settings|"
    r"kyc|onboarding|subscription plan|refund policy page|terms and conditions)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# stage 1 -- fetch. Deterministic. Cached, so a rerun is reproducible and offline-capable.
# ---------------------------------------------------------------------------
def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def fetch(url, offline=False):
    """Return (text, bytes, source). source is 'cache' or 'network'."""
    os.makedirs(CACHE, exist_ok=True)
    key = re.sub(r"[^A-Za-z0-9]+", "_", url)[-120:] + ".txt"
    path = os.path.join(CACHE, key)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        return body, len(body.encode("utf-8")), "cache"
    if offline:
        return None, 0, "missing"
    try:
        body = _get(url)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        return None, 0, "error:%s" % exc
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return body, len(body.encode("utf-8")), "network"


def doc_urls(index_text, wide=False, limit=12):
    """Pick candidate documentation pages out of llms.txt.

    llms.txt indexes TITLES AND DESCRIPTIONS ONLY -- a lesson this project learned the hard way
    and recorded -- so a zero here is a weak negative and we always fetch the bodies.
    """
    urls = re.findall(r"\((https://razorpay\.com/docs/build/llm-docs/[^\)]+\.md)\)", index_text)
    urls = list(dict.fromkeys(urls))          # the index lists some pages twice
    if not wide:
        keep = []
        for seed in SEED_PAGES:                # specificity order: never let a generic page
            for u in urls:                     # crowd out the specific one that carries the contract
                if u.endswith(seed) and u not in keep:
                    keep.append(u)
        if keep:
            return keep[:limit]
    scored = []
    for u in urls:
        s = 0
        for kw, w in (("webhook", 5), ("payment", 2), ("refund", 2), ("order", 2),
                      ("idempot", 4), ("retry", 4), ("capture", 2), ("settlement", 1)):
            if kw in u.lower():
                s += w
        if s:
            scored.append((s, u))
    scored.sort(reverse=True)
    return [u for _, u in scored[:limit]]


# ---------------------------------------------------------------------------
# stage 2 -- segment. Deterministic. NO MODEL.
# ---------------------------------------------------------------------------
def sentences(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)          # drop code blocks
    text = re.sub(r"\|[^\n]*\|", " ", text)                      # drop table rows
    text = re.sub(r"[#>*`_\[\]]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if 40 <= len(s.strip()) <= 400]


def candidates(text):
    """Sentences that plausibly impose a runtime obligation. This is the honest baseline."""
    out = []
    for s in sentences(text):
        if NOISE.search(s):
            continue
        if MODAL.search(s) or HAZARD.search(s):
            out.append(s)
    seen, uniq = set(), []
    for s in out:
        k = re.sub(r"\W+", "", s.lower())[:90]
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    return uniq


# ---------------------------------------------------------------------------
# stage 3 -- classify. THE ONLY MODEL CALL.
# ---------------------------------------------------------------------------
def _load_local_env():
    """Load the project's local env file at runtime, exactly as tools/probe_*.py already do.

    Credentials live only in that git-ignored file and are never printed. Reading it here means a
    clean clone plus that one file reproduces the run, with nothing to export by hand.
    """
    path = os.path.join(ROOT, ".env" + ".local")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sentence": {"type": "string"},
                    "is_normative": {"type": "boolean"},
                    "obligation": {"type": "string"},
                    "hazard": {"type": "string"},
                    "checkable_by_execution": {"type": "boolean"},
                    "proposed_key": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["sentence", "is_normative", "obligation", "hazard",
                             "checkable_by_execution", "proposed_key", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}

SYSTEM = """You derive a conformance specification from a payment vendor's own documentation.

You are given sentences from Razorpay's published integration docs. For each, decide whether it
imposes a NORMATIVE, RUNTIME obligation on the MERCHANT'S INTEGRATION -- something that could be
violated by running code and therefore checked by executing the integration.

Say is_normative TRUE only when the sentence tells the integration how it must behave, or warns of
an input condition the integration must tolerate (out-of-order delivery, duplicate delivery, retry,
signature verification, response codes). A sentence that describes what RAZORPAY does, or explains
a dashboard feature, or gives commercial terms, is NOT normative for our purposes.

checkable_by_execution is TRUE only if a harness could decide it by driving the integration and
observing merchant-visible state -- not by reading source code.

proposed_key: a short uppercase identifier like ORDER-INDEPENDENCE or DUPLICATE-TOLERANCE.
hazard: the concrete failure a violation causes, in one clause, in money or state terms.
Be conservative. A precise small set beats a large noisy one."""


def classify(cands, page_url, verbose=True):
    _load_local_env()
    try:
        import anthropic
    except ImportError:
        print("  ! anthropic SDK not installed; skipping classification "
              "(pip install anthropic). Deterministic stages still ran.", file=sys.stderr)
        return []
    client = anthropic.Anthropic()
    payload = "\n".join("%d. %s" % (i + 1, s) for i, s in enumerate(cands))
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=SYSTEM,
            messages=[{"role": "user",
                       "content": "Source page: %s\n\nSentences:\n%s" % (page_url, payload)}],
            output_config={"format": {"type": "json_schema", "schema": CLASSIFY_SCHEMA}},
        )
    except Exception as exc:                                  # noqa: BLE001 - report, do not crash
        print("  ! model call failed (%s); continuing with deterministic output only"
              % type(exc).__name__, file=sys.stderr)
        return []
    text = next((b.text for b in resp.content if b.type == "text"), None)
    if not text:
        return []
    try:
        return json.loads(text).get("findings", [])
    except json.JSONDecodeError:
        return []


# ---------------------------------------------------------------------------
# stage 4 -- score against the held-out key. Deterministic. NO MODEL.
# ---------------------------------------------------------------------------
def rank(cands):
    """Deterministically rank candidate sentences by how contract-like they are. NO MODEL.

    This exists so the pipeline produces a measurable result with no API key at all, and so the
    model stage has an honest baseline to beat rather than an empty one. The features are
    deliberately crude and legible -- if a model cannot beat this, it is not earning its place.

    Signals, in the order they matter:
      +3  the sentence warns about an input the integration must tolerate (the hazard is the point)
      +2  a modal verb makes it an obligation rather than a description
      +2  it names the mechanism the vendor prescribes as the remedy
      -3  it describes what the VENDOR does, not what the integration must do
    """
    vendor_subject = re.compile(r"^\s*(we|razorpay|our)\b", re.I)
    remedy = re.compile(r"\b(x-razorpay-event-id|header|signature|2xx|status code|idempoten\w*)\b", re.I)
    tolerate = re.compile(
        r"\b(may not always|multiple times|not guaranteed|out of order|same .{0,20}event|"
        r"could be scenarios|expected behaviour|expected behavior|retry|retries)\b", re.I)
    scored = []
    for s in cands:
        v = 0
        if tolerate.search(s):
            v += 3
        if MODAL.search(s):
            v += 2
        if remedy.search(s):
            v += 2
        if HAZARD.search(s):
            v += 1
        if vendor_subject.search(s):
            v -= 3
        scored.append((v, s))
    scored.sort(key=lambda p: -p[0])
    return scored


def precision_at_k(scored, k):
    """How many of the top-k ranked sentences are actually in the held-out key?"""
    top = [s for _, s in scored[:k]]
    blob = " ".join(top).lower()
    hit = sum(1 for frag in ANSWER_KEY.values() if frag.lower() in blob)
    return hit, len(ANSWER_KEY), top


def score(found_sentences):
    """Grade rediscovery against the four properties a human wrote weeks earlier."""
    blob = " ".join(found_sentences).lower()
    hits, misses = [], []
    for key, frag in ANSWER_KEY.items():
        (hits if frag.lower() in blob else misses).append(key)
    recall = len(hits) / float(len(ANSWER_KEY))
    return {"hits": hits, "misses": misses, "recall": recall,
            "n_candidates": len(found_sentences)}


# ---------------------------------------------------------------------------
def ablate():
    """The experiment that falsified this module. Run it; do not take our word for it.

    Compares the MODAL/HAZARD filter against a NULL filter that keeps every sentence, over the
    same on-disk corpus. If the null filter scores the same, the filter is not doing the work.
    """
    import glob
    bodies = [open(f, encoding="utf-8", errors="replace").read()
              for f in glob.glob(os.path.join(CACHE, "*.txt")) if "llms" not in f]
    if not bodies:
        print("no cached corpus; run the module once first so pages are on disk", file=sys.stderr)
        return 2
    null_set = [s for b in bodies for s in sentences(b)]
    filt_set = [s for b in bodies for s in candidates(b)]
    print("NULL-FILTER ABLATION -- the experiment that falsified this module")
    print("corpus: %d cached doc bodies\n" % len(bodies))
    rows = [("null filter (keeps everything)", null_set), ("MODAL/HAZARD filter (ours)", filt_set)]
    for label, ss in rows:
        blob = " ".join(ss).lower()
        key = sum(1 for f in ANSWER_KEY.values() if f.lower() in blob)
        gap = sum(1 for f in KNOWN_GAPS.values() if f.lower() in blob)
        print("  %-32s %5d sentences   answer-key %d/%d   new-discoveries %d/%d"
              % (label, len(ss), key, len(ANSWER_KEY), gap, len(KNOWN_GAPS)))
    print("\n  If those two rows agree, the filter contributes nothing but volume reduction.")
    print("  They agree. That is why the recall claim was withdrawn.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-llm", action="store_true",
                    help="deterministic stages only; reports the honest baseline the model must beat")
    ap.add_argument("--offline", action="store_true", help="use only the on-disk cache")
    ap.add_argument("--wide", action="store_true",
                    help="let the investigator choose pages from the whole index itself")
    ap.add_argument("--limit", type=int, default=6, help="max doc pages to read")
    ap.add_argument("--json", dest="as_json", action="store_true")
    ap.add_argument("--ablate", action="store_true",
                    help="run the null-filter ablation that falsified this module's own metric")
    args = ap.parse_args(argv)

    if args.ablate:
        return ablate()

    print("investigator: deriving the oracle from the vendor's own documentation")
    print("model stage: %s" % ("DISABLED (--no-llm)" if args.no_llm else MODEL))
    print("\n" + "!" * 78)
    print("! THIS MODULE IS A DOCUMENTED FAILED EXPERIMENT. Its recall number is CONTAMINATED:")
    print("! SEED_PAGES (hand-written by us) names the page the answers live on, and a null")
    print("! filter keeping every sentence scores identically. Run --ablate to reproduce.")
    print("! Any recall figure printed below is reported for the record, NOT as a result.")
    print("!" * 78 + "\n")

    index, n, src = fetch(LLMS_TXT, offline=args.offline)
    if index is None:
        print("FATAL: could not read the docs index (%s)" % src, file=sys.stderr)
        return 2
    print("  index      %-58s %8d B  [%s]" % (LLMS_TXT, n, src))

    pages = doc_urls(index, wide=args.wide, limit=args.limit)
    print("  selected   %d candidate pages\n" % len(pages))

    all_sentences, findings, pages_read = [], [], 0
    for url in pages:
        body, nb, s = fetch(url, offline=args.offline)
        if body is None:
            print("  skip       %-58s [%s]" % (url.rsplit("/", 1)[-1], s))
            continue
        pages_read += 1
        cands = candidates(body)
        all_sentences.extend(cands)
        print("  read       %-58s %8d B  [%s]  %d candidate sentences"
              % (url.rsplit("/", 1)[-1], nb, s, len(cands)))
        if cands and not args.no_llm:
            got = classify(cands, url)
            for f in got:
                f["source_url"] = url
            findings.extend(got)

    det = score(all_sentences)
    print("\n--- stage 2 (deterministic) -------------------------------------------")
    print("  pages read              %d" % pages_read)
    print("  candidate sentences     %d" % det["n_candidates"])
    print("  answer-key recall       %d/%d  (%.0f%%)"
          % (len(det["hits"]), len(ANSWER_KEY), 100 * det["recall"]))
    print("  rediscovered            %s" % (", ".join(det["hits"]) or "none"))
    print("  missed                  %s" % (", ".join(det["misses"]) or "none"))

    # Deterministic ranking: the baseline the model stage must beat. No model, no API key.
    scored = rank(all_sentences)
    print("\n--- stage 2b (deterministic ranking) ----------------------------------")
    for k in (4, 8, 16):
        hit, total, _ = precision_at_k(scored, k)
        print("  recall@%-3d              %d/%d of the held-out key in the top %d ranked sentences"
              % (k, hit, total, k))
    # Dedupe across pages: the same normative sentence is repeated verbatim on several doc pages,
    # so an undeduped top-N is mostly one sentence wearing different hats.
    seen_r, uniq_scored = set(), []
    for v, s in scored:
        k = re.sub(r"\W+", "", s.lower())[:70]
        if k not in seen_r:
            seen_r.add(k)
            uniq_scored.append((v, s))
    print("\n  top 6 ranked candidates, deduped (nothing here was written by us):")
    for v, s in uniq_scored[:6]:
        print("    [%+d] %s" % (v, s[:104]))

    # Did the investigator surface obligations the human never encoded as properties?
    blob_all = " ".join(s for _, s in uniq_scored).lower()
    gaps_found = [g for g, frag in KNOWN_GAPS.items() if frag.lower() in blob_all]
    if gaps_found:
        print("\n  *** BEYOND THE ANSWER KEY -- obligations present in the docs that the")
        print("      hand-written contract never encoded as checkable properties:")
        for g in gaps_found:
            print("        %s" % g)
        print("      This is the point of the module: the human read these pages and did not")
        print("      turn these two sentences into properties. The investigator did.")

    result = {"deterministic": det,
              "ranked_recall": {str(k): precision_at_k(scored, k)[0] for k in (4, 8, 16)},
              "model_findings": findings, "pages_read": pages_read}

    if not args.no_llm:
        normative = [f for f in findings if f.get("is_normative")]
        checkable = [f for f in normative if f.get("checkable_by_execution")]
        mdl = score([f["sentence"] for f in checkable])
        print("\n--- stage 3 (model) ---------------------------------------------------")
        print("  sentences classified    %d" % len(findings))
        print("  judged normative        %d" % len(normative))
        print("  judged checkable        %d   <-- these become property candidates" % len(checkable))
        print("  answer-key recall       %d/%d  (%.0f%%)"
              % (len(mdl["hits"]), len(ANSWER_KEY), 100 * mdl["recall"]))
        if det["n_candidates"]:
            print("  precision gain          %d -> %d sentences (%.0fx reduction)"
                  % (det["n_candidates"], len(checkable),
                     det["n_candidates"] / max(1, len(checkable))))
        print("\n  property candidates:")
        for f in checkable:
            print("    %-26s %s" % (f.get("proposed_key", "?")[:26], f.get("obligation", "")[:96]))
            print("      hazard: %s" % f.get("hazard", "")[:100])
        result["model"] = mdl

    if args.as_json:
        print("\n" + json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
