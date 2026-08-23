# ADR 0001 — The oracle is a specification, not a regression baseline

**Status:** accepted · **Date:** 2026-08-23

## Context
Existing tooling that executes code to find defects (Greptile TREX, CI suites, AI code review) decides
correctness by comparison against a prior state: a passing baseline, an existing test suite, the
behaviour before a pull request. That answers *"did this change break something?"*

The defects in this repository did not break anything. They have been in shipped releases for a long
time. There is no PR, no regression, and no green baseline to diff against.

## Decision
The oracle is derived from the **vendor's published contract**, not from the code's own history. Each
property in `harness/contract.py` carries the verbatim documentation sentence that makes it normative,
and the report prints those citations alongside the verdicts so a reviewer can audit the premise as
easily as the result.

## Consequences
- We can decide correctness for code that was never right. A regression oracle structurally cannot.
- We are constrained to properties the vendor actually documents. We do not get to invent invariants
  we merely believe in — `P5-AMOUNT-INTEGRITY` is included because Razorpay implements it twice in
  their own code, not because it seemed sensible to us.
- If the vendor's documentation is wrong, our oracle inherits that. Stated in `LIMITATIONS.md`.
- Properties the vendor documents but we cannot decide from outside are reported **YELLOW**, never
  guessed. `P3` is permanently structural for this reason.
