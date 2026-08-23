# ADR 0003 — No model in the verdict path

**Status:** accepted · **Date:** 2026-08-23

## Context
A 2026 study of 86,156 test-file patches from Codex, Copilot, Devin, Cursor and Claude Code found
**80.2% contain weak or no explicit oracle signals.** Execution is solved; knowing whether the answer
was right is not. A model-judged verdict is exactly the evidence a payments reviewer will not accept.

## Decision
Every verdict this harness emits is decided by a hand-written comparison against a contract-derived
expectation. **No language model is consulted anywhere in the verdict path.**

Where a model is genuinely load-bearing — reading an unfamiliar integration to produce its adapter
(endpoint, event alphabet, payload shape, state query) — it sits strictly **outside** the verdict, and
its output is a fixture that the deterministic oracle then judges.

## Consequences
- Verdicts are reproducible and auditable by someone who does not trust us.
- The harness cannot handle a target nobody has written an adapter for. Accepted: `harness/targets.py`
  makes the adapter surface explicit and small — four fields.
- Deliberately declining to use a model in the verdict is a design decision, not an omission, and it
  is why the mutation corpus can be believed at all.
