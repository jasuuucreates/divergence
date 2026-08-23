# ADR 0004 — A model may propose properties; only a deterministic gate may ratify them

**Status:** accepted · **Date:** 2026-08-23

## Context
The specification was five hand-written properties. Razorpay publish every documentation page as
markdown, indexed from a 496 KB `llms.txt` — a machine-readable statement of the contract a merchant
is expected to honour, almost none of which is ever tested. Reading 455 candidate sentences and
deciding which state a checkable obligation is open-ended comprehension over unfamiliar prose;
writing it as code would mean writing an English parser.

But a model-proposed property is a hypothesis. Shipping hypotheses as a specification is how a
conformance tool becomes an LLM wrapper.

## Decision
Split the pipeline so that the model's output is always an input to something deterministic.

1. `harness/specmine.py` — **no model.** Fetches and hashes the corpus, splits it into sentences,
   keeps those carrying normative force. Output: candidates, not properties.
2. A model proposes, for a candidate sentence, a property and the experiment that would decide it.
3. `harness/gate.py` — **no model.** Four checks, all deterministic:
   - **G1 GROUNDED** — the quoted sentence appears byte-for-byte in the fetched corpus
   - **G2 EXPRESSIBLE** — it maps to an experiment template the rig implements
   - **G3 DECIDABLE** — that experiment can observe what the property talks about
   - **G4 NON-VACUOUS** — some variant of the integration actually violates it
4. `harness/vacuity.py` supplies G4 by running the whole suite against deliberately altered
   integrations and recording which properties ever fail.

## Consequences
- **G1 is an anti-fabrication check with teeth.** It rejected two of our own citations that had been
  reconstructed from numbered list items and table cells rather than quoted. Both were fixed; the
  gate was also relaxed to ignore list markers, because that is document structure rather than prose
  — but only after the citations themselves were corrected. Loosening the check alone would have
  been the wrong half of the repair.
- **G4 rejects properties that cannot fail.** It found P2 vacuous: our duplicate-tolerance check
  compared only order *status*, which is identical whether an order is refunded once or twice, so it
  was blind to double-refunding by construction. The observable was widened and P2 is now
  falsifiable. It also rejects P3 permanently — P3 is structural and can only return YELLOW, so it is
  an advisory, not a property, and the gate says so rather than letting it inflate the count.
- The specification can grow from documentation without the growth being trusted on the model's word.
- Cost: the gate can only ratify properties whose experiment already exists. A true sentence about
  settlement timing is reported UNDECIDABLE rather than ratified. That is the correct answer, and it
  is reported as a distinct outcome from REJECTED.
