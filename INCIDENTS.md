# Incident log

Every time this project produced a wrong result, the wrong result is recorded here with the date, how
it was caught, and what changed. Nothing is removed once written.

The reason for keeping it is narrow and practical: **a harness that makes claims about someone else's
production code has to show its own error rate.** Four of the claims we published in earlier drafts
were false. If that is invisible, the surviving claims are worth less, not more.

Entries are newest first.

---

## 2026-08-23 — The stub was the only component with no test, and it was wrong

**Symptom.** `harness/stubcheck.py`, written specifically to test the thing that had never been
tested, found four fields — `contact`, `description`, `email`, `method` — that are in Razorpay's
documented Payments Entity, are read by the integrations under test, and were **not** being returned
by our stub.

**Cause.** The stub returned the ten fields we happened to need when we wrote it. Every behavioural
verdict in this project is mediated by that stub, and `LIMITATIONS.md` had always said "the stub is
not Razorpay" — but a disclaimer is not a measurement, and nothing was checking it.

**Fix.** The stub now returns every documented field the integrations read, and `stubcheck.py` runs
as part of the suite. It sorts differences into three buckets and only one of them can invalidate a
verdict: documented **and** read **and** missing.

**Did it change anything?** No. The full suite was re-run after the fix and every verdict is
identical — P1 RED, P2 GREEN, P4 RED, P5 RED, and the two-target matrix still RED/GREEN. That is now
a measured statement rather than a hope, which is the only reason it is worth writing down.

---

## 2026-08-23 — The same setup error killed five runs before it explained itself

**Symptom.** `KeyError: 'ORDER_ID'` from `rig.new_order()`, five separate times.

**Cause.** Only one gateway plugin can be active at a time, so any EDD run leaves WooCommerce
switched off. `new_order.php` needs `wc_create_order()`, so it produced nothing, and the harness died
on a dictionary lookup that reads like a harness bug rather than the setup problem it is.

**Fix.** `new_order()` now reports the cause: which plugins are active, why that is wrong, and the
command that fixes it. `coverage.py` activates its target explicitly and verifies the switch, as
`matrix.py` and `corpus.py` already did.

**Why it mattered.** Not because the failure was dangerous — it was loud. Because five occurrences of
one confusing error is a signal that the error message, not the operator, is the defect.

---

## 2026-08-23 — The harness reported GREEN when it had measured nothing

**Symptom.** `harness/check.py` decided P1 with:

```python
states = {t["terminal"]["order_status"] for t in trials}
verdict = "GREEN" if len(states) == 1 else "RED"
```

**Cause.** If every trial returns `order_status = None` — a dead rig, an order that was never
created, a SQL call that returned nothing — that set has size one, and the property reports **GREEN**.
The harness announces the integration conforms on the basis of having observed nothing. P2 and P5 had
the same shape: two all-`None` states compare equal, and `None` is not in the set of paid statuses.

**Fix.** `harness/measured.py` guards every property, and `UNMEASURED` now outranks every other
verdict in the summary — a run that could not observe the integration has neither cleared it nor
condemned it. Two seed-spec tests enforce both halves.

**Why it mattered.** This is the *fourth* appearance of one shape in this project: absence of evidence
scored as evidence of absence. The false-negative CONVERGENT run, the corpus rows that measured
nothing, the vacuity checker that passed vacuously, and now this. It is no longer treated as a
recurring mistake to be careful about; it is a shared, tested guard.

---

## 2026-08-23 — A property that could not fail was being reported as a pass

**Symptom.** `harness/vacuity.py` ran the full suite against several deliberately altered
integrations and found P2 returned GREEN on every one.

**Cause.** P2 compared only `order_status`. That status is identical whether an order was refunded
once or twice, so the property was blind to double-refunding **by construction**. We had been
publishing "P2 GREEN" as though it were evidence of idempotence; it was evidence of nothing, because
we had never shown the check *could* fail.

**Fix.** The observable was widened — `rig.terminal_state()` now also reports `refund_count` and
`refunded_total` — and P2 redelivers the *last* event rather than the first. A variant was then built
specifically to break idempotence (`p2-nonidempotent-refund`), and P2 goes RED on it. P2 is now
falsifiable, so its GREEN on the real plugin means something.

**Something learned on the way.** The plugin *is* idempotent on refunds, but not because it checks:
its "already refunded" branch logs and falls through **without returning**. What actually prevents a
second refund is WooCommerce refusing to over-refund the order. The idempotence is inherited from the
host, not implemented by the integration.

**Also:** P3 remains permanently vacuous, and correctly so. It is structural and can only ever return
YELLOW, so the gate rejects it as an advisory rather than letting it inflate the property count.

---

## 2026-08-23 — Two of our own citations were reconstructed, not quoted

**Symptom.** `harness/gate.py`'s G1 check — the quoted sentence must appear byte-for-byte in the
fetched documentation corpus — rejected two of our own five properties.

**Cause.** Both sentences *are* in the corpus, but our recorded quotes were assembled rather than
quoted. P3 concatenated three numbered list items into one "sentence"; P5 prepended a table cell
(`amount : integer`) and included a `₹295` that Razorpay's own markdown export strips.

**Fix.** In this order: the citations were corrected to single contiguous sentences that exist
verbatim, **and then** `normalise()` was taught to ignore ordered-list markers, which are document
structure rather than prose. Loosening the check alone would have been the wrong half of the repair.

**Why it mattered.** This is a milder version of the fabricated-citation incident below — nothing was
invented, but nothing was verbatim either. The difference between the two is smaller than it feels,
and only an automated check catches it reliably.

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
