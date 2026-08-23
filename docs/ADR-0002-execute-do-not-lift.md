# ADR 0002 — Run whole projects over HTTP; never lift fragments

**Status:** accepted · **Date:** 2026-08-22 · **Supersedes:** the original extract-and-eval design

## Context
The first design extracted the signature-verification function out of generated integration code and
executed it in isolation. It was tested before being committed to. **It failed: 1 of 3 targets ran,
and only partially.** Regex extraction produced code one target could not even parse.

## Decision
Do not extract. Build the integration as it actually ships, run it in a container, and drive it over
**HTTP** exactly as the payment provider would.

## Consequences
- Faithful: we test what a merchant deploys, not a fragment lifted out of it.
- Language-agnostic: one corpus, one HTTP client, N targets, no per-language parser or grammar.
- Some findings only *exist* at the HTTP boundary — a handler that answers 500 where it should answer
  400 has no in-process representation at all.
- Costs a Docker toolchain and per-target setup. Accepted; `rig/setup.sh` is one command and CI runs
  it so a reviewer does not have to.
- The terminal state must be read **after** deferred queues drain, or the measurement captures the
  delay rather than the behaviour — and hands a reviewer the rebuttal *"that is a transient our cron
  fixes."*
