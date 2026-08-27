# Divergence

**When two systems disagree about your money, the party who is right usually cannot prove it —
because nobody kept an independent record of what actually happened.**

Merchants have been telling Razorpay a version of this since 2017. The shop says the order failed;
the dashboard says the payment was captured; the money has already left the customer. At least
**eleven issues** on their own tracker, [two open today](#the-reports-this-comes-from). One merchant
measured it at **4-5% of their orders** and waited nearly four years for a reply. Another had their
webhook configured with exactly the two events this harness proves can change the outcome depending
only on which arrives first.

Nobody could reproduce that class of failure on demand. So each report got answered with a guess —
or closed without a fix.

**This reproduces it.** It is a conformance harness: it runs the real integration and checks it
against the payment provider's own published contract.

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

And `harness/coverage.py` says what a GREEN actually covers. Two events in the alphabet are
**units** — verified by execution to leave the terminal state unchanged at *every* insertion
position — so any sequence containing them is equivalent to the same sequence without them:

| length | orderings | classes to run | | basis |
|---|---|---|---|---|
| 3 | 64 | **15** | 4x | **executed** — `evidence/coverage.json` |
| 6 | 4096 | **127** | 32x | *computed from the same unit set; not executed* |

The length-3 row is a certificate: the units were verified by running each event at **every**
insertion position and observing the terminal state was unchanged. A GREEN there covers 64 orderings
from 15 runs.

**The length-6 row is arithmetic, not a result.** It is what the collapse *would* give if the two
units remain units in longer contexts, which we have not run. There is no length-6 certificate in
`evidence/`, and this table says so rather than letting the bigger number imply one. Unit-hood is
*observed*, not proved, and the certificate says that in those words too.

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
TP 5   FN 0   TN 3   FP 0        recall 1.00    precision 1.00    (n=8, P5 only)
```

**Read the scope before the number.** Every one of those eight mutants targets **P5** alone, so this
measures detection of *that* defect class — not of the harness as a whole. Presenting it as a harness
figure would be an overstatement, and it was presented that way in an earlier draft.

Whether the *other* properties can fail at all is a separate question, answered separately by
`harness/vacuity.py`:

| property | verdicts ever observed | |
|---|---|---|
| P1 order independence | GREEN, RED | falsifiable |
| P2 duplicate tolerance | GREEN, RED | falsifiable |
| P4 no silent loss | RED | falsifiable |
| P5 amount integrity | RED | falsifiable |
| P3 event-id dedup | YELLOW only | **cannot fail — advisory, not a property** |

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

## Where the model is, and where it is deliberately not

Razorpay publish every documentation page as markdown under `/docs/build/llm-docs/`, indexed from a
496 KB `llms.txt`. That is a machine-readable statement of the contract a merchant is expected to
honour. `harness/specmine.py` fetches and hashes it — **343 pages, 11,282 sentences** — and filters
to **455 candidate sentences** that look normative. No model is involved in that step; it is regex
and bookkeeping.

**A model reads those 455 sentences and proposes properties**: which sentences state a checkable
obligation, and what experiment would decide each one. That is the one job here that is genuinely
open-ended comprehension over unfamiliar prose. Writing it as code would mean writing an English
parser, and it would be worse.

**A proposed property is a hypothesis, not a specification.** So `harness/gate.py` ratifies it, and
the gate contains no model at all — four deterministic checks:

| gate | asks |
|---|---|
| **G1 GROUNDED** | does the quoted sentence appear **byte-for-byte** in the fetched corpus? |
| **G2 EXPRESSIBLE** | does it map to an experiment this rig actually implements? |
| **G3 DECIDABLE** | can that experiment observe the thing the property talks about? |
| **G4 NON-VACUOUS** | does *any* mutant in the corpus violate it? |

```
$ python harness/gate.py --self-test
corpus: 343 documentation pages, fetched and hashed

  P1-ORDER-INDEPENDENCE    RATIFIED
  P2-DUPLICATE-TOLERANCE   RATIFIED
  P3-EVENT-ID-DEDUP        REJECTED
      FAIL G4-NON-VACUOUS   no mutant in the corpus violates it -- this property cannot fail
  P4-NO-SILENT-LOSS        RATIFIED
  P5-AMOUNT-INTEGRITY      RATIFIED

  RATIFIED 4   REJECTED 1   UNPROVEN 0
```

**G4 is the one that matters, and it rejected one of our own properties.** A property that nothing
can violate reports green forever; it is decoration, not a test. P3 survives in this repository only
as an advisory signal, explicitly marked, and it is excluded from the verdict.

G1 has caught us too. It rejected **three** citations that had been reconstructed rather than
quoted — one a paraphrase, one a concatenation of two list items, one with a table cell prepended.
Every one of them read as a plausible sentence from Razorpay's docs. None of them was.

**So: the model proposes, and nothing it proposes is trusted.** It never sees a verdict, never
touches merchant state, and no output of it reaches a published number without passing four checks
that are pure code. There is no orchestration framework here because there is no model in the
verdict path — there would be nothing for it to orchestrate.

*Design rationale in [docs/ADR-0003](docs/ADR-0003-no-model-in-the-verdict.md) and
[docs/ADR-0004](docs/ADR-0004-gated-specification.md).*

---

## The documentation says otherwise

In April 2026 Razorpay merged an agent-authored PR adding `docs/flows/webhook-flow.md` to
razorpay-woocommerce. It is on `master` today. Line 5:

> *"The plugin processes them asynchronously to prevent timeout issues and **ensure idempotent order
> processing**."*

Its Idempotency Handling table lists four checks. All four are single-event state guards — *has this
already happened?* — and **the 197-line document contains no treatment of out-of-order delivery
anywhere.** Idempotency and order-independence are different properties.

A second claim, lines 80–81, describes the event store as read-then-append. It never appends: a type
confusion makes the read return `[]` every time, so each event overwrites the last.

**Both that document and this project used AI. The difference is where.** A model read the source and
concluded the path was idempotent — which is what careful source-reading produces, and is wrong in a
way only execution reveals. Here the model's job stops at proposing what to check; the verdict is a
deterministic comparison against executed state.

The guards in that document are real and do prevent the duplicates they were written for. This is not
a claim that anyone was careless. See [docs/DOCS-VS-BEHAVIOUR.md](docs/DOCS-VS-BEHAVIOUR.md).

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

## The reports this comes from

These are Razorpay's own public issues, opened by merchants, read directly rather than summarised:

| | | |
|---|---|---|
| [#631](https://github.com/razorpay/razorpay-woocommerce/issues/631) | *"all successful payments ... incorrectly marked as **Failed**"* — money deducted, provider says captured, shop says failed. *"forces our team to **manually verify every 'failed' order** against the Razorpay dashboard"* | **open, 9 months** |
| [#591](https://github.com/razorpay/razorpay-woocommerce/issues/591) | *"the payment gets captured immediately, but the order status ... takes **1 to 2 hours** to update"* | **open, 15 months** |
| [#181](https://github.com/razorpay/razorpay-woocommerce/issues/181) | *"almost **4-5% of the orders** — customer is paying ... but either the order status is not updated or shows pending"* · *"We tried raising this issue a couple of times but no reply."* | open ~4 years |
| [#571](https://github.com/razorpay/razorpay-woocommerce/issues/571) | webhook configured with *"2 active events: `payment.authorized` and `refund.created`"* — the exact pair whose arrival order changes the terminal state here | closed |
| [#183](https://github.com/razorpay/razorpay-woocommerce/issues/183) | *"duplicate stock reduction, order status changes twice, two emails each"* — the idempotency property, P2 | closed |

**What this is not.** These reports are *not* proof that the defect demonstrated in this repository
caused any of them. The symptoms are consistent and #571's configuration is a striking match, but
causation was never established for a single one of them, and no claim is made that any ticket was
solved here. Nor is this the most common complaint about the plugin — reading the WordPress.org
reviews, that is support responsiveness and onboarding, not webhook correctness.

The claim is narrower and it is the one the evidence supports: **this failure class is real,
recurring, reported by real merchants, and until now could not be reproduced on demand.**

## Limits, and claims we withdrew

Read [LIMITATIONS.md](LIMITATIONS.md) before the results. Four claims published in earlier drafts were
**withdrawn after our own checking disproved them** — including a headline percentage that turned out
to be an artefact of how we sampled. They are listed with reasons rather than deleted.

## Disclosure

Both channels are filed. The private report went first, and this repository was published after it.

| finding | channel | filed |
|---|---|---|
| Correctness defects (P1, P4, P5) | [razorpay/razorpay-woocommerce#664](https://github.com/razorpay/razorpay-woocommerce/issues/664) — public | **25 August 2026** |
| One separate security-class finding | Razorpay HackerOne programme, report **3966083** — private | **24 August 2026** |

**"Filed" means submitted, not accepted.** Razorpay's
[`SECURITY.md`](https://github.com/razorpay/razorpay-mcp-server/blob/main/SECURITY.md) places open
source repositories outside their bug-bounty scope, so report 3966083 may be closed rather than
triaged. The only claim made here is that it was reported privately before anything was published,
on a date Razorpay can check against their own records. If they close it, that will be recorded here
in the same words.

Their HackerOne asset list contains no source-repository entry and GitHub private vulnerability
reporting is disabled on the repo (`{"enabled": false}`), so the report was filed against the closest
available asset with the mismatch stated in its first paragraph. There was no cleaner private channel
to use.

Everything described in this repository is a **correctness defect** — no attacker, no privilege
boundary crossed — which is why it can be discussed openly. The security-class finding is **not**
described here, is not shown in the video, and will not be published unless and until Razorpay
indicate they are content for it to be.

*An earlier revision of this file asserted the private report had already been sent. It had not.
That sentence was written when the disclosure was planned rather than done, and it stayed in the
file after the plan slipped. It is recorded in [INCIDENTS.md](INCIDENTS.md) rather than quietly
corrected, because a project whose argument is "do not report what you did not measure" cannot
publish a claim about its own conduct that it has not yet earned.*

## Prior art, named

Yang et al. (NDSS 2017) did differential testing of payment SDKs — the technique is not new, the
target is. [Greptile TREX](https://greptile.com) ships sandbox execution and test generation per PR.
[Antithesis](https://antithesis.com) ships deterministic simulation testing. `hookdeck/webhook-skills`
covers ~170 providers. MCPSafe published MCP annotation findings against GitHub's own server in May
2026. None of them asks whether a payment integration conforms to its provider's documented delivery
contract.
