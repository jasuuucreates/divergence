#!/usr/bin/env python
"""
Making the documentation executable -- stage 3: the gate.

A language model is genuinely useful for one job here, and only one: reading 455 candidate sentences
of vendor prose and proposing which of them state a checkable obligation, and what experiment would
decide each. That is open-ended comprehension over unfamiliar text, and writing it as code would mean
writing an English parser.

But a model-proposed property is a HYPOTHESIS, not a specification. This module is what turns one
into the other, and every check in it is deterministic. Nothing here consults a model.

    G1  GROUNDED     the quoted sentence appears byte-for-byte in the fetched corpus
    G2  EXPRESSIBLE  it maps to one of the experiment templates the rig actually implements
    G3  DECIDABLE    the experiment can observe what the property talks about
    G4  NON-VACUOUS  at least one mutant in the corpus violates it

G1 exists because I once wrote a citation myself and presented it as a quotation from Razorpay, in
the file whose entire premise is that every property carries a real source sentence (INCIDENTS.md,
2026-08-23). A rule enforced by discipline is not enforced. This one is enforced by a substring
search against a corpus that was fetched, hashed and dated.

G4 is the interesting one. A property that no mutant can violate is not a test -- it is a sentence
that will report GREEN forever regardless of the code under it. Shipping such a property inflates
the apparent size of the specification while measuring nothing. This is the same reasoning behind
mutation testing's use of a test suite's mutation score, applied to the specification instead of the
tests, and it is the check that stops a model from padding the property list.

    python harness/gate.py --proposals spec/proposals.json
    python harness/gate.py --self-test         # gate the 5 hand-written properties
"""
import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORPUS = os.path.join(ROOT, "spec", "corpus")

sys.path.insert(0, HERE)
import contract  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------------------------
# G2/G3: the experiment templates the rig actually implements. A proposal that does not map to one
# of these is not rejected because it is wrong -- it is rejected because WE CANNOT DECIDE IT, which
# is a different thing and is reported as such.
# ---------------------------------------------------------------------------------------------
TEMPLATES = {
    "reorder": {
        "does": "deliver the same event multiset in two or more legal orders; compare terminal states",
        "observes": ["order_status"],
        "implemented_by": "harness/check.py::check_order_independence",
    },
    "redeliver": {
        "does": "deliver an event, then deliver it again; compare terminal states",
        "observes": ["order_status"],
        "implemented_by": "harness/check.py::check_duplicate_tolerance",
    },
    "fault": {
        "does": "force the upstream payment fetch to fail, then inspect what the queue recorded",
        "observes": ["order_status", "queue_cron_status", "stored_events"],
        "implemented_by": "harness/check.py::check_no_silent_loss",
    },
    "mismatch_amount": {
        "does": "deliver an authorized payment whose amount differs from the order total",
        "observes": ["order_status"],
        "implemented_by": "harness/check.py::check_amount_integrity",
    },
    "static_grep": {
        "does": "search the integration source for a required token",
        "observes": ["source"],
        "implemented_by": "evidence/scripts/survey_eventid.py",
        "structural": True,
    },
}

# What each template can actually see. A proposal about settlement timing, TLS versions or dashboard
# configuration is undecidable here no matter how normative its sentence is.
OBSERVABLE = {"order_status", "queue_cron_status", "stored_events", "http_status", "source"}


def load_corpus():
    """Every byte of documentation we fetched, as one searchable blob per file."""
    if not os.path.isdir(CORPUS):
        raise SystemExit("no corpus. Run:  python harness/specmine.py --fetch")
    return {fn: io.open(os.path.join(CORPUS, fn), encoding="utf-8").read()
            for fn in os.listdir(CORPUS) if fn.endswith(".md")}


def normalise(s):
    """Whitespace, emphasis and list markers vary between the rendered page and the raw markdown;
    none of them should decide whether a citation is real.

    Ordered-list markers are stripped for the same reason backticks are: "1. " is document
    structure, not part of the sentence. This was added after the gate correctly rejected two of
    our own citations that spanned numbered list items -- the citations were also fixed, because
    loosening the check alone would have been the wrong half of the repair.
    """
    s = re.sub(r"[*_`]", "", s)
    s = re.sub(r"(?m)^\s*\d+\.\s+", " ", s)     # "1. " at line start
    s = re.sub(r"(?<=[.:])\s*\d+\.\s+", " ", s)  # "... . 2. ..." mid-paragraph
    return re.sub(r"\s+", " ", s).strip().lower()


def g1_grounded(quote, corpus):
    """Does this sentence actually exist in the documentation we fetched?

    Checked as a substring over the normalised text. An ellipsis is allowed to join two sentences
    from the same page, so each fragment is checked independently.
    """
    fragments = [f for f in re.split(r"\s*\.\.\.\s*", quote) if len(f.strip()) > 25]
    if not fragments:
        return False, "quote too short to verify"
    hits = []
    for frag in fragments:
        n = normalise(frag)
        found = [fn for fn, body in corpus.items() if n in normalise(body)]
        if not found:
            return False, "fragment not found in corpus: %r" % frag[:70]
        hits.append(found[0])
    return True, "grounded in " + ", ".join(sorted(set(hits)))


def g2_expressible(template):
    if template not in TEMPLATES:
        return False, "no experiment template named %r (have: %s)" % (
            template, ", ".join(sorted(TEMPLATES)))
    return True, "maps to %s" % TEMPLATES[template]["implemented_by"]


def g3_decidable(template, observes):
    t = TEMPLATES.get(template)
    if not t:
        return False, "no template"
    unknown = [o for o in observes if o not in OBSERVABLE]
    if unknown:
        return False, "the rig cannot observe %s" % ", ".join(unknown)
    missing = [o for o in observes if o not in t["observes"] and not t.get("structural")]
    if missing:
        return False, "template %r does not observe %s" % (template, ", ".join(missing))
    return True, "observes %s" % ", ".join(observes)


def g4_non_vacuous(prop_key, corpus_results):
    """Is there any mutant that makes this property fail?

    corpus_results is the output of harness/corpus.py: mutant -> observed verdict per property.
    A property never violated by any mutant is not a test of anything. It is reported REJECTED with
    that reason rather than silently shipped, because a specification padded with unfalsifiable
    clauses looks larger and measures less.
    """
    if not corpus_results:
        return None, "no mutation results available -- run harness/corpus.py first"
    reds = [m for m, v in corpus_results.items() if v.get(prop_key) == "RED"]
    if not reds:
        return False, "no mutant in the corpus violates it -- this property cannot fail"
    return True, "violated by %d mutant(s): %s" % (len(reds), ", ".join(sorted(reds)[:3]))


def gate(proposal, corpus, corpus_results=None):
    """Run every check. A proposal is RATIFIED only if none returns False."""
    checks = []
    ok, why = g1_grounded(proposal.get("doc_quote", ""), corpus)
    checks.append(("G1-GROUNDED", ok, why))
    ok, why = g2_expressible(proposal.get("template"))
    checks.append(("G2-EXPRESSIBLE", ok, why))
    ok, why = g3_decidable(proposal.get("template"), proposal.get("observes", []))
    checks.append(("G3-DECIDABLE", ok, why))
    ok, why = g4_non_vacuous(proposal.get("key"), corpus_results)
    checks.append(("G4-NON-VACUOUS", ok, why))

    hard_fail = [c for c in checks if c[1] is False]
    unknown = [c for c in checks if c[1] is None]
    verdict = "REJECTED" if hard_fail else ("UNPROVEN" if unknown else "RATIFIED")
    return {"key": proposal.get("key"), "verdict": verdict,
            "checks": [{"gate": g, "pass": p, "why": w} for g, p, w in checks]}


def self_test(corpus, corpus_results):
    """Gate our own five hand-written properties. If the gate cannot ratify the properties we
    already trust, the gate is wrong -- and that is worth finding out before using it on anything
    a model produced."""
    tmpl = {"P1-ORDER-INDEPENDENCE": ("reorder", ["order_status"]),
            "P2-DUPLICATE-TOLERANCE": ("redeliver", ["order_status"]),
            "P3-EVENT-ID-DEDUP": ("static_grep", ["source"]),
            "P4-NO-SILENT-LOSS": ("fault", ["order_status", "queue_cron_status"]),
            "P5-AMOUNT-INTEGRITY": ("mismatch_amount", ["order_status"])}
    props = []
    for p in contract.ALL_PROPERTIES:
        t, obs = tmpl[p.key]
        props.append({"key": p.key, "doc_quote": p.doc_quote, "template": t, "observes": obs})
    return props


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proposals", help="JSON file of model-proposed properties")
    ap.add_argument("--self-test", action="store_true",
                    help="gate the five hand-written properties instead")
    ap.add_argument("--corpus-results", default=os.path.join(ROOT, "spec", "property_mutants.json"))
    a = ap.parse_args()

    corpus = load_corpus()
    results = None
    if os.path.exists(a.corpus_results):
        results = json.load(io.open(a.corpus_results, encoding="utf-8"))

    if a.self_test:
        props = self_test(corpus, results)
        title = "SELF-TEST -- gating the five hand-written properties"
    elif a.proposals:
        props = json.load(io.open(a.proposals, encoding="utf-8"))
        props = props.get("proposals", props)
        title = "GATING %d MODEL-PROPOSED PROPERTIES" % len(props)
    else:
        raise SystemExit("give --proposals FILE or --self-test")

    print("=" * 100)
    print(title)
    print("=" * 100)
    print("corpus: %d documentation pages, fetched and hashed\n" % len(corpus))

    out, counts = [], {"RATIFIED": 0, "REJECTED": 0, "UNPROVEN": 0}
    for p in props:
        r = gate(p, corpus, results)
        out.append(r)
        counts[r["verdict"]] += 1
        print("  %-24s %s" % (r["key"], r["verdict"]))
        for c in r["checks"]:
            mark = "ok  " if c["pass"] else ("FAIL" if c["pass"] is False else "?   ")
            print("      %s %-16s %s" % (mark, c["gate"], c["why"][:88]))
        print()

    print("=" * 100)
    print("  RATIFIED %d   REJECTED %d   UNPROVEN %d"
          % (counts["RATIFIED"], counts["REJECTED"], counts["UNPROVEN"]))
    print("=" * 100)
    dest = os.path.join(ROOT, "spec", "gated.json")
    io.open(dest, "w", encoding="utf-8").write(json.dumps({"counts": counts, "results": out}, indent=2))
    print("saved -> %s" % os.path.relpath(dest, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
