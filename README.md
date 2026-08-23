# Divergence

**A conformance harness for payment integrations. It runs the integration and checks it against its
payment provider's own published contract.**

Razorpay's webhook documentation states two things:

> *"Ideally, you should receive a webhook in the order in which the webhook events occur.
> **However, you may not always receive the webhooks in the order.**"*
>
> *"There could be scenarios where your endpoint might receive the same webhook event multiple times.
> **This is an expected behaviour based on the webhook design.**"*

Those sentences are a specification. This harness turns them into executable properties and points
them at real integrations.

---

## The result

Same two events. Same signatures. Same payloads. **Only the arrival order differs.**

```
refund.created  then  payment.authorized   ->  wc-processing
payment.authorized  then  refund.created   ->  wc-refunded
```

`wc-processing` means **paid — fulfil this order.** The customer has been refunded at Razorpay, and
the shop believes it was paid and will ship the goods.

This is not a race that sometimes goes wrong. `payment.authorized` is parked for a cron that only
selects rows older than **300 seconds**, while refunds are handled synchronously on arrival. **Any
refund issued within five minutes of an authorization takes the losing path by construction.**

An exhaustive search over 64 delivery schedules gives the exact boundary:

> **A set of events diverges if and only if it contains at least one `payment.authorized`
> and at least one `refund.created`.** — 20 of 20 event-sets predicted correctly.

---

## It distinguishes correct code from incorrect code

The same harness, the same property, the same underpaid delivery, against two of Razorpay's own
official plugins:

| | `razorpay-woocommerce` | `razorpay-edd` |
|---|---|---|
| ₹499 order, ₹1 paid | **RED** — order reaches `wc-processing` | **GREEN** — payment marked `failed` |

WooCommerce's `paymentAuthorized()` computes the expected amount and never compares it. The **same
file** compares it on the virtual-account path (`razorpay-webhook.php:505`), and `razorpay-edd`
compares it at line 130. Two sibling code paths enforce the invariant; the main one does not.

A harness that reports RED everywhere is a bug list. **The GREEN is the point.**

---

## Measured detection

Eight mutants, applied to both plugins in both directions, each a single reversible edit with the
file's sha256 recorded before and after:

```
TP 5   FN 0   TN 3   FP 0        recall 1.00    precision 1.00    (n=8)
```

What makes the composition meaningful:

- **Three defects injected into `razorpay-edd`** — code this harness was never developed against.
- **Two of those are subtle**: the comparison stays and still *reads* like a check
  (`$payment['amount'] === $payment['amount']`). Grep-based tooling sees a comparison and passes it.
  Only executing with a mismatched amount tells them apart.
- **Two noise mutants** (a log string, a reworded comment) left the verdict unmoved — the harness
  keys on behaviour, not text.
- **One repair** produced no false positive.

**n=8 and the corpus is self-authored.** These numbers bound behaviour on the defect classes we
thought of. They are not a population estimate. See [LIMITATIONS.md](LIMITATIONS.md).

---

## Why existing tools do not find this

**Stock Semgrep across the generated integration templates: 2 findings, both an unrelated Django CSRF
rule.** CodeQL's only relevant query is *both* experimental *and* deprecated, and is excluded from
every default suite.

These are not patterns in a file. They are properties of a **system under a delivery schedule**. You
cannot grep for *"reaches a different terminal state depending on arrival order."*

And a regression checker cannot help either:

| | asks | needs |
|---|---|---|
| Regression oracle — CI, AI code review, Greptile TREX | *"did this change break something?"* | a PR, a baseline, an existing suite |
| **Specification oracle — this** | *"is this correct?"* | only the vendor's published contract |

**A regression oracle is structurally blind to code that was never right.** There is no PR here and
nothing regressed. Greptile's CEO put the first half well — *"could not have been caught with more
inference; they required code execution"* — and execution is now solved. The **oracle** is not.

Payments is one of the few domains where a specification oracle is writable, because the contract is
public: the vendor's docs, and the fact that money is integer paise.

---

## Reproduce it

```bash
cd rig && ./setup.sh              # WordPress + WooCommerce + the unmodified plugin, one command
cd rig && ./setup-edd.sh          # adds the second target (razorpay-edd) to the same rig

python harness/matrix.py          # BOTH targets, one property, one command  <- start here
python harness/check.py           # all five properties against WooCommerce, ~85s, exit 1 on RED
python harness/causality.py       # patch the blamed line, watch the verdict flip, then restore
python harness/search.py          # enumerate delivery schedules, report divergence
python harness/corpus.py          # the mutation corpus and its confusion matrix
```

`matrix.py` is the shortest path to the point of this project: the same property, the same underpaid
delivery, RED for one of Razorpay's plugins and GREEN for the other.

Every number in this repository comes from a transcript in [`evidence/`](evidence/), and every
transcript names the command that produced it. The plugins under test are cloned at pinned refs and
verified byte-identical before and after every run.

## The contract

Every property carries the verbatim vendor sentence that makes it normative. Print them without
running anything:

```bash
python harness/contract.py
```

| | property | kind | woocommerce | edd |
|---|---|---|---|---|
| P1 | all legal orderings converge to the same terminal state | behavioural | **RED** | n/a¹ |
| P2 | redelivery does not change the terminal state | behavioural | GREEN | n/a¹ |
| P3 | `x-razorpay-event-id` is used to identify duplicates | structural | YELLOW² | YELLOW² |
| P4 | an accepted event changes state or is durably recorded | behavioural | **RED** | n/a¹ |
| P5 | an order must not reach a paid state for the wrong amount | behavioural | **RED** | **GREEN** |

¹ EDD dispatches exactly one event and has no deferred queue, so P1/P2/P4 cannot fail there **by
construction**. Reported as not-applicable, never as evidence of care.
² Structural, advisory only. **6 of 6** official Razorpay plugins never mention the header their own
docs prescribe — but absence of the prescribed mechanism is not proof of non-idempotence. **P2
decides idempotence by execution.**

## Limits, and claims we withdrew

Read [LIMITATIONS.md](LIMITATIONS.md) before the results. Four claims published in earlier drafts were
**withdrawn after our own checking disproved them** — including a headline percentage that turned out
to be an artefact of how we sampled. They are listed with reasons rather than deleted.

## Disclosure

Findings of a security class were reported to Razorpay privately through their published channel and
are **not** described here or demonstrated on video. Everything documented in this repository is a
**correctness defect** — no attacker, no privilege boundary crossed — which is why it can be
discussed openly.

## Prior art, named

Yang et al. (NDSS 2017) did differential testing of payment SDKs — the technique is not new, the
target is. [Greptile TREX](https://greptile.com) ships sandbox execution and test generation per PR.
[Antithesis](https://antithesis.com) ships deterministic simulation testing. `hookdeck/webhook-skills`
covers ~170 providers. MCPSafe published MCP annotation findings against GitHub's own server in May
2026. None of them asks whether a payment integration conforms to its provider's documented delivery
contract.
