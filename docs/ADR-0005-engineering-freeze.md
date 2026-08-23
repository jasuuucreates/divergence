# ADR 0005 — Freeze the engineering

**Status:** accepted · **Date:** 2026-08-24 · **Decided by:** the engineer, not the calendar

## Context

The system works and is validated end to end. Seven independent checks pass on a clean run: the seed
spec, the contract's own citations, the gate self-test (4 ratified / 1 rejected), the demo preflight,
stub fidelity (zero critical gaps), the full conformance run, and the two-target matrix.

The remaining time is not unlimited, and the binding constraint is no longer engineering. It is a
five-minute video (~20 hours) and the ability to defend the work unaided (~10 hours) — neither of
which any additional feature helps with, and both of which additional features actively harm, because
every new capability is one more thing to explain under questioning.

## What was considered and rejected

**Generalising the docs-vs-behaviour finding.** The strongest recent result is that Razorpay's own
agent-authored `docs/flows/webhook-flow.md` claims idempotent order processing that execution
disproves. The obvious next move is to check agent-authored documentation across their other repos
and turn an anecdote into a pattern.

Checked first: **only `razorpay-woocommerce` has agent-authored architecture docs.** `razorpay-magento`
returns zero agent-related files in its tree. Building a cross-repo documentation checker would be
building for N=1. Killed on evidence.

**A third target.** `razorpay-magento` requires an entire Magento stack — roughly a day of Docker work
— for the same argumentative value already obtained from `razorpay-edd`, which demonstrated
discrimination (RED on one plugin, GREEN on the other) at a fraction of the cost. Marginal.

**More properties.** The gate deliberately rejects any property whose experiment the rig cannot run,
so adding properties means adding experiment templates: multi-day work whose output is a longer list,
not a stronger argument. The specification is small on purpose, and every property in it is
falsifiable.

## Decision

**Stop adding functionality.** Remaining work is limited to: fixing anything found to be wrong,
running CI once the repository is pushed, and supporting the video and rehearsal.

## What this is not

It is not "we ran out of time". Two capabilities were added *today* — the query trace and the
guard-audit test — because both made the system harder to fool rather than larger. The line is not
effort, it is whether a change increases the number of things that must be defended or decreases the
number of ways the system can be wrong.

## Consequences

- The last engineering act was closing the seventh instance of one defect class with an audit test
  rather than a patch, which is the right note to stop on: the recurring failure can no longer be
  reintroduced silently.
- CI remains unverified until the first push, and the repository says so rather than implying a green
  badge exists.
- If implementation evidence later invalidates a claim, that is a reason to reopen. Wanting a
  larger feature list is not.
