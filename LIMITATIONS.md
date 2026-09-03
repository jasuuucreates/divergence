# LIMITATIONS

*Written before the README, deliberately: it is easier to write an honest headline once the limits
are already on paper.*

This document exists because the harness makes claims about somebody else's production code. Every
claim below is bounded, and the bounds are stated before anyone has to ask.

---

## 1. What the harness actually observes

It observes the **merchant-visible terminal state** of an order — the row a shop owner would see —
after every deferred queue has drained. It does not observe Razorpay's side of the transaction, the
customer's bank, or anything the plugin does not persist.

**Consequence:** where the truth is not visible from outside the database, the harness returns
**YELLOW**, not a guess. A property it cannot decide is reported as undecided.

## 2. The stub is not Razorpay

To drive an order to a paid state offline, `api.razorpay.com` is replaced by a local stub
(`rig/stub/router.php`). The plugin under test is **byte-identical** — the SDK is repointed by a
WordPress mu-plugin using the vendored `Api::setBaseUrl()`, and the plugin directory's sha256 is
verified before and after every run.

**But be clear about what this means:** in stub mode we are testing **the plugin's handling of a
Razorpay-shaped response**, not Razorpay. A behaviour that depends on a real API nuance we did not
reproduce would not be caught here.

## 3. Fault injection is induced, not observed in the wild

Property P4 runs with the upstream payment fetch forced to return HTTP 500. That failure was
**induced deliberately**; we did not observe it happening in production. The mechanism it exposes —
a queue row marked consumed while the order never moved, and never retried — fires in production on
any transient upstream failure (timeout, 5xx, rate limit), but **we have not measured how often that
occurs**, and we do not claim a frequency.

The trigger is encoded in the payment id (`pay_FAULT…`) rather than in server configuration,
specifically so it is visible in the request transcript and cannot be mistaken for a spontaneous
failure.

## 4. The search is bounded, and absence of a finding is not absence of a defect

`search.py` enumerates delivery schedules over the four events the plugin's own dispatch switch
handles, to a fixed length. It does **not** explore: crash-restart between handler steps, concurrent
delivery, the browser callback racing the webhook, secret-rotation windows, or subscription events.

**A GREEN result therefore means "no divergence at this length over this alphabet", never "correct".**
Where a search completed without finding anything, we say so — a bounded negative result is
reportable and we report it.

## 5. The mutation corpus is self-authored

The seeded defects used to measure detection were written by us. That is a real limitation and it is
the standard one for this kind of work: we can only measure detection of defect classes we thought
of. Razorpay's own AI playbook calls this a **cold-start set** and endorses building one from domain
expertise before production traces exist — but naming the practice does not remove the circularity.

**We publish the corpus, the mutants, the pre-registered expectations and the full confusion
matrix** ([`harness/corpus.py`](harness/corpus.py), [`evidence/corpus.json`](evidence/corpus.json)),
so the measurement can be disputed on its merits rather than taken on trust.

The measured result is **TP 5 · FN 0 · TN 3 · FP 0 — recall 1.00, precision 1.00 at n=8.**
**Never quote those figures without "n=8, self-authored."** Eight mutants is enough to show the
verdict tracks the defect and does not move under irrelevant edits; it is nowhere near enough to
estimate how often this class of defect occurs in the wild, and we make no such claim.

Three of the eight are injected into `razorpay-edd` — code this harness was never developed against —
which is the direction that matters. A detector that only works on its own development codebase is
not a detector.

## 6. Provenance of the findings — stated plainly

**The headline defects were found by reading the source, not by the harness.** The harness was built
afterwards to reproduce them from the contract, and it does. A later schedule search rediscovered the
ordering divergence by enumeration, without being told where to look, and established its exact
boundary — which improves the provenance but does not change the origin.

One finding does have independent provenance: **P5 (amount integrity) came out of correcting a claim
we had already retracted.** Establishing what was actually true about amount verification produced
the observation that `paymentAuthorized()` never compares the paid amount to the ordered amount,
while two sibling code paths do.

We say all of this rather than let the repo imply otherwise.

## 7. Claims we withdrew, and why

Kept visible on purpose. Each was believed, then disproved by our own checking.

| Withdrawn claim | Why |
|---|---|
| *"6.62% of prices lose a paisa"* | A property of **uniform-random sampling**, not of any catalogue. Same price ending, same defect, **20× different rate** depending only on the range sampled (`.99` is 11.88% over ₹1–5,000 and 0.59% over ₹1–1,00,000). No single percentage is defensible, so we assert none. |
| *"Every webhook destroys the stored event history"* | False. `saveWebhookEvent()` has exactly one call site, inside `case PAYMENT_AUTHORIZED`. No other event touches that table. The correct, narrower claim is about a **second** authorization. |
| *"6 of 7 plugins do not verify the amount paid"* | Arithmetically unsupported by our own survey file, which records `verifies_amount: true` for WooCommerce. Two of our own survey scripts also disagreed with each other on file paths. The survey method was not reliable enough to publish and was cut. |
| The MCP `readOnlyHint` finding | Not novel. MCPSafe published the same class against GitHub's own MCP server on 13 May 2026. We cite them; we claim nothing. |

## 8. What we did not verify

- Whether Razorpay's plugins de-duplicate by some mechanism other than `x-razorpay-event-id`.
  Absence of the header proves the **prescribed** mechanism is absent, not that the integration is
  non-idempotent. That is why P3 is marked **structural** and can only ever return YELLOW.
- Whether any of these defects has caused a specific merchant a specific loss. We have no such data
  and do not imply any.
- Anything about `razorpay-magento`, `-prestashop`, `-whmcs`, `-cscart` beyond the single
  literal-string check in §C4. We did not run them.

## 9. Disclosure

Findings of a security class were reported to Razorpay privately through their published channel
before publication and are **not** described here or demonstrated on camera. The defects documented
in this repository are **correctness defects** — no attacker, no privilege boundary crossed — which
is why they can be discussed openly.

---

*If something here is wrong, the fastest way to show it is to run the harness. Every number in this
repository comes from a committed transcript, and every transcript is listed in
`evidence/README.md` with the command that regenerates it.*
