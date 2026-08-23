# Incident log

Every time this project produced a wrong result, the wrong result is recorded here with the date, how
it was caught, and what changed. Nothing is removed once written.

The reason for keeping it is narrow and practical: **a harness that makes claims about someone else's
production code has to show its own error rate.** Four of the claims we published in earlier drafts
were false. If that is invisible, the surviving claims are worth less, not more.

Entries are newest first.

---

## 2026-08-23 — The corpus measured nothing for two of its eight rows

**Symptom.** The first mutation-corpus run returned `UNKNOWN` for both `razorpay-woocommerce` rows,
in 7–8 seconds. A real run takes ~22 seconds.

**Cause.** The corpus activates exactly one gateway plugin per row, because both Razorpay plugins
define the same constants. It activated `razorpay-woocommerce` **before** `woocommerce`, which
`razorpay-woocommerce` depends on. WP-CLI reported a non-zero exit that nothing was reading, the
plugin stayed inactive, and the probe then died on a `KeyError` that read like a harness bug rather
than a setup bug.

**Fix.** Dependency-ordered activation, plus a hard assertion on the resulting active plugin set that
raises rather than returning a row (`harness/corpus.py::activate`).

**Why it mattered.** A corpus row whose setup silently failed is worse than a missing row — it looks
like a measurement. Had those two rows returned `GREEN` instead of `UNKNOWN`, the confusion matrix
would have reported two false negatives that were really two setup failures.

---

## 2026-08-23 — The harness scored correct code as RED

**Symptom.** First run against `razorpay-edd` reported `P5-AMOUNT-INTEGRITY: RED`, against a
prediction of GREEN registered before the run.

**Cause.** Our predicate was `GREEN if terminal == "pending" else RED`. It assumed an implementation
that refuses an underpayment leaves the order untouched. EDD does something stricter: it marks the
payment **`failed`**. The oracle scored a correct refusal as a defect.

**Fix.** The predicate became `RED iff terminal ∈ PAID_STATES`. Refusing quietly and refusing loudly
are both conformant; only accepting is not. The original predicate and the reasoning are kept in
`harness/edd_probe.py`.

**Why it mattered.** **A false positive against correct code is worse than a false negative** — it
accuses someone's work. It was caught only because the expected verdict was written down *before* the
run (`harness/targets.py::expectations`) and the mismatch was loud.

---

## 2026-08-23 — Two searches ran concurrently and corrupted each other

**Symptom.** A schedule search created ~107 orders where 64 trials should create 64.

**Cause.** The same search was launched twice — once with `nohup`, once through a background runner.
Python buffers stdout when it is not a terminal, so the first run produced no output and was assumed
dead. It was not. `rig.drain()` runs the WordPress cron, and **that cron drains every eligible row in
the table, not just the caller's** — so each run was consuming the other's parked events at arbitrary
points in their sequences.

**Fix.** `harness/runlock.py` — a lockfile that refuses to start a second rig job. Long runs now use
`python -u` so liveness is visible.

**Why it mattered.** This is *the same defect class this harness reports in `razorpay-woocommerce`*:
concurrent consumers of one shared queue with no mutual exclusion. We built it into the tool we built
to find it. Both runs were discarded; neither is recorded as a result.

---

## 2026-08-23 — A citation in the contract file was fabricated

**Symptom.** `harness/contract.py` carried this as the vendor quotation for P5:

> *"Razorpay's API accepts amounts in the smallest currency sub-unit (paise), as an integer, precisely
> so that the amount charged is exactly the amount intended."*

**Cause.** That sentence does not exist. It was written by us and presented as a citation, in a file
whose entire premise is that every property carries the verbatim source sentence.

**Fix.** Replaced with a sentence actually fetched from Razorpay's API documentation, and annotated in
place to say what the quote does and does not establish — it fixes the *units*, not the invariant. The
normative force of P5 comes from Razorpay's own code implementing the check twice and omitting it once.

**Why it mattered.** We had spent days auditing research output for fabricated quotations before doing
it ourselves. A rule you only enforce against others is not a rule.

---

## 2026-08-23 — A headline percentage was an artefact of our sampling

**Symptom.** We published *"6.62% of prices lose a paisa"* to floating-point truncation.

**Cause.** It was measured over **uniform-random paise**. Real catalogues do not price uniformly. Rate
by price ending, measured exhaustively:

| ending | ₹1–5,000 | ₹1–1,00,000 |
|---|---|---|
| `.00` `.25` `.50` `.75` | 0.00% | 0.00% |
| `.99` | 11.88% | **0.59%** |
| `.90` | 19.60% | 19.57% |
| `.29` | 0.04% | **18.35%** |

The same price ending and the same defect give a **20× different rate** depending only on the range
sampled. `.00` and `.50` are exact in binary floating point and are never affected.

**Fix.** The percentage is withdrawn entirely. What we claim now is deterministic and needs no
distribution: `int(amount*100)` undercharges by one paisa on a specific, checkable set of prices —
₹8.95 → 894 not 895; ₹16.90 → 1689 not 1690. The defect is certain; the population rate is not ours
to assert.

**Why it mattered.** A reviewer who asks *"what price distribution?"* ends the conversation. The
honest version is weaker as a headline and much stronger as a claim.

---

## 2026-08-23 — "Every webhook destroys the stored event history" was false

**Symptom.** We stated that any webhook overwrites the plugin's stored event list.

**Cause.** `saveWebhookEvent()` has exactly one call site, inside `case self::PAYMENT_AUTHORIZED`.
No other event touches that table.

**Fix.** Narrowed to what is true and demonstrable: a **second** `payment.authorized` arriving after
the first has been drained overwrites the stored event, resets `rzp_webhook_notified_at`, and leaves
`rzp_update_order_cron_status` at 2 — while the drain query selects only rows with status 0. The
second authorization becomes permanently unselectable. Observed live.

**Why it mattered.** The narrower claim is more severe than the broad one, and unlike the broad one it
survives someone opening the file.

---

## 2026-08-23 — Two of our own survey scripts disagreed with each other

**Symptom.** `evidence/scripts/survey_plugins.py` and `survey_plugins2.py` returned different verdicts
on which plugins verify the paid amount.

**Cause.** Three separate errors: one script probed guessed file paths and missed two plugins
entirely; the amount-check pattern matched `get_total()` — a *getter*, not a comparison; and one run
selected `Model/WebhookEvents.php` for Magento, which is an admin dropdown list, not a handler.

**Fix.** Every semantic pattern-match over unfamiliar source was discarded. The only cross-plugin
claim that survives is a literal-string absence check — whether the handler mentions
`x-razorpay-event-id` at all — verified against the correct handler for each plugin and reproducible
with one line of `curl | grep`. **Both broken scripts are kept in `evidence/scripts/`** rather than
deleted.

**Why it mattered.** When two runs of your own instrument disagree, the instrument is the finding.

---

## 2026-08-22 — The first fix for the ordering defect made it worse

**Symptom.** The causality test patched the line the harness blames and the verdict did not move.

**Cause.** The patch deferred the refund into the existing queue instead of dropping it. Two things
were wrong, both discovered by reading the code afterwards: the cron's switch handles **only**
`case 'payment.authorized'`, so a deferred `refund.created` is stored and then ignored forever; and
`saveWebhookEvent()` overwrites rather than appends, so parking the refund would have **destroyed the
stored authorization**.

**Fix.** A minimal diagnostic patch that disables the guard instead. That one flips P1 from RED to
GREEN and moves nothing else. Both attempts are kept in `harness/causality.py`.

**Why it mattered.** A patch that makes the bug worse is exactly what a causality test is for. It also
means we do not propose the deferral as a remedy.
