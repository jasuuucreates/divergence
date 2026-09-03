# Incident log

Every time this project produced a wrong result, the wrong result is recorded here with the date, how
it was caught, and what changed. Nothing is removed once written.

The reason for keeping it is narrow and practical: **a harness that makes claims about someone else's
production code has to show its own error rate.** Four of the claims we published in earlier drafts
were false. If that is invisible, the surviving claims are worth less, not more.

Entries are newest first.

---

## 2026-09-04 — We attacked our own harness and 13 of 19 attacks succeeded

Everything in this repo argues that a tool must not report a result it has not earned. So the day
before submission we wrote a suite whose only job was to make this harness report a GREEN it had not
earned — `tests/adversarial.py`, 19 tests, no Docker, about two seconds.

**13 of them succeeded against the code we were about to ship.** They are listed below with what a
wrong result would have looked like. All 19 pass now. When this was first written that sentence ended "and the suite runs in CI" -- which was not true: `.github/workflows/conformance.yml` did not reference the file. An unverified claim about our own verification, inside the entry about unverified claims. The workflow now runs it in the `seed-spec` job, so the sentence is true because the file changed, not because the sentence was softened.

| what was wrong | what a wrong result looked like |
|---|---|
| `causality.py` printed `sha(TARGET) == sha(TARGET)` as its restore check | Always `True`. The one module that **modifies the vendor plugin** verified the restore with a tautology, and the README cited that line as proof the plugin was returned byte-for-byte. |
| `check.py` — the centrepiece — had no control arm | Deactivate `razorpay-woocommerce`, leave `woocommerce` active: orders still create, the endpoint is simply unregistered, every schedule ends `wc-pending`. That is a real string, so the evidence guard is satisfied — and then P1 sees one state (GREEN), P2 sees two identical states (GREEN), P5 sees a non-paid status (GREEN). **Three GREENs off a plugin that is switched off.** |
| `matrix.py` and `corpus.py` read a verdict out of a child probe's stdout without reading its control arm | `edd_probe.py` printed `CONTROL FAILED … nothing below is trustworthy` and then printed its verdict line anyway. The headline discrimination artefact would reproduce the 2026-08-23 false-GREEN incident *through the tool built to demonstrate discrimination*. |
| `edd_probe.py`'s control was an inequality against the pending state | `status()` shells out to wp-cli. A dead container returns `""`; a PHP fatal returns an error string. **Neither equals the pending state**, so the one arm that ever caught a false GREEN passed on every kind of total failure except the one it was written for. |
| `search.py` could print *"No divergence found … that is a real result"* over an all-`None` run | It also contained `import measured` and never called it — a fix someone started and abandoned, which made the module look guarded to anyone skimming imports. |
| `rig.sql()` and `rig.wp()` discarded the return code | A dead database, a wrong password, a container that is not up, and a query that legitimately matched no rows all produced **the same empty string**. Every guard above this layer was trying to tell absence from failure using a signal that had already thrown the distinction away. This is the root cause under three of the other entries. |
| `rig.deliver()` returned curl's `000` as an ordinary non-2xx | "The endpoint refused this event" and "the endpoint was never reached" arrived at the oracle as the same fact. A stopped container read as conformance. |
| `rig.drain()` ran the cron once and verified nothing | The README's claim that verdicts are taken on a **converged** state — the claim that makes *"your cron would have fixed it later"* unavailable as a rebuttal — was not enforced anywhere in the code. It is now a fixpoint test. |
| `check_duplicate_tolerance()` compared refund counts but required only the status to exist | If the refund query failed, both trials carried `None`, `None == None` compared equal, and **P2 silently reverted to exactly the status-only comparison `vacuity.py` caught it doing.** The fix for vacuity un-applied itself the first time a query failed. |
| `corpus.py` dropped unscored rows from the confusion matrix and exited 0 | The CI gate on our own detection metric was **satisfiable by measuring nothing**: every mutant failing to produce a verdict yields fp=0, fn=0, clean exit. A green badge earned by a run that detected nothing. |
| `stubcheck.documented_fields()` could return `[]` and report success | The instrument that validates our instrument passed hardest when it had read nothing. |
| `amount_integrity.py`'s GREEN branch raised `TypeError` | The format operand was attached to the second line, which has no placeholder. **The only branch in that module that can say "the plugin is correct" had never once successfully executed** — which is why nobody noticed. |

A fourteenth instance was then found by applying the *pattern* rather than the list:
`corpus.py` recorded `sha_restored` for each of its eight mutants and compared it to nothing, while
its docstring claimed the sha was "recorded before, during and after". That module edits the vendor
plugin eight times in a row, so a restore that silently failed would have made every later mutant a
measurement of the previous mutant's leftovers. It now captures the sha before the edit and refuses
to continue if the restore does not match.

### The part worth reading
While writing the suite, **three first-draft tests passed against broken code** because they grepped
for a word and found it in prose — one matched the word "control" inside a docstring, one matched a
variable name inside a `print()`, one had a non-greedy regex walk out of the function and into the
next one's `raise`. The adversarial suite's own first draft was an instance of the failure class it
exists to find. They were caught by *running* it, not by reading it.

### Then the live rig, attacked eleven ways
`harness/redteam.py` had been written, reviewed and **never run** — its outcomes were labelled
predictions. They were executed the same day: **10 decidable attacks, all held; 1 undecidable.**

Three of the eleven had to be repaired before they could be believed, and each repair is the same
lesson as the rest of this entry:

- **`no-drain` neutralised the wrong thing.** It replaced `drain()` with a no-op lambda — a stronger
  adversary than reality, and unfalsifiable, because with the function gone no guard inside it could
  ever fire. Rewritten to neutralise the *cron* and leave `drain()` live, it immediately found a real
  hole in the fixpoint check added that morning: **a queue row that never started moving is also a
  fixpoint.** `drain()` now also requires that nothing is left unconsumed.
- **`oversize` accused correct code.** Its predicate was "the order did not move", but a 12 MB
  validly-signed body that is *fully processed* is responsibility taken **and discharged**. Only
  "claimed the queue row and left the order pending" is silent loss. Scoring correct code as RED is
  already an incident in this log; doing it to the vendor rather than to ourselves would be worse,
  because that is the accusation we publish.
- **`db-down` could not hold its own precondition.** `docker-compose.yml` declares
  `cli: depends_on: db: service_healthy`, so the harness's own wp-cli path restarts the database the
  attack had just stopped. It reported BROKEN on the strength of a verdict table full of real data —
  an experiment that never ran under the condition it was named for. It now checks, and reports
  **UNDECIDABLE**. The runner grew a third outcome so that "measured nothing" can never again be
  counted as either a pass or a finding.

Also fixed: a criterion that required the literal string `OVERALL=UNMEASURED` while its own stated
expectation was *"UNMEASURED, **or an abort**"* — so `check.py` refusing correctly, with zero GREENs,
was scored as BROKEN. And a summary line that printed `0 of 1 attacks BROKE` immediately after
printing `BROKEN`, because the control-arm break happened before the counter.

**What the surviving attacks bought.** `real-clock` is the one that matters: `drain()` backdates a
timestamp so the plugin's 300-second window opens at once, and a reader may fairly say *you
falsified the clock*. One trial with no backdating, waiting the real 320 seconds, reached the
**identical** terminal state. `event-id` promoted P3 from a grep result to a behavioural one and
closed a gap nobody had noticed — the rig never sent `X-Razorpay-Event-Id` at all, so P2's GREEN had
been measured without the prescribed mechanism present. `sig` established that every RED in this
repository was measured through a door that actually authenticates.

### Verified by intervention, not by assertion
Fixing a guard proves nothing unless the guard fires. Both were tested by breaking the rig on purpose:

```
razorpay-woocommerce deactivated  ->  check.py: 0 verdicts printed, exit 1,
                                      "REFUSING TO RUN: the control arm did not move a fresh
                                       order into a paid state"
razorpay-edd deactivated          ->  edd_probe.py: P5-AMOUNT-INTEGRITY: UNDECIDABLE, exit 2,
                                      zero GREEN lines anywhere in the output
```

Then both were reactivated and the full verdict reproduced unchanged: P1 RED, P2 GREEN, P4 RED,
P5 RED, P3 YELLOW, OVERALL RED, exit 1 — now above a control arm that passes. **The guards changed
when a verdict may be issued. They changed no finding.**

### What this cost us
The honest accounting: `check.py` went from about 110s to about 151s, because a control arm is a
real trial and a fixpoint test is a second cron round. We took the time.

---

## 2026-08-24 — The README claimed a disclosure that had not happened

**Symptom.** `README.md` stated: *"Findings of a security class were reported to Razorpay privately
through their published channel."* No such report had been filed.

**Cause.** The sentence was written while the disclosure was being *planned*, as part of drafting how
the repository would describe itself. The plan then slipped by a day, and the sentence stayed. Nothing
was invented — the intent was real and the drafts exist — but the file asserted a completed action in
the past tense.

**Why it is the worst class of error in this project.** Every other incident here is a wrong technical
claim. This one is a wrong claim about our own conduct, in the section a reviewer would read to decide
whether we behaved responsibly. Had it shipped, the repository would have told a payments company we
had notified them when we had not.

**Fix.** The section now carries an explicit `NOT YET FILED` status, placeholder fields for the date
and reference of each channel, and a line stating that the repository must not be published until
those are filled. The correction is recorded here rather than quietly edited.

**Caught by** re-reading the repository against reality before pushing, rather than by anything
automated — which is the honest answer, and the reason the pre-push checklist now exists.

---

## 2026-08-24 — The same defect, the seventh time, and the point at which we stopped fixing sites

**Symptom.** `harness/search.py` reports *"No divergence found at length N over this alphabet"* and
this repository quotes that as a meaningful negative result — it bounds where the defect is not. On a
dead rig every terminal state is `None`, every multiset group then contains exactly one distinct
state, and the search reports that it bounded the defect having measured nothing.

`harness/causality.py` had the matching shape: two failed arms both yield `None`, the equality branch
fires, and it concludes **NOT CAUSAL** from two absences.

**Cause.** The same one as the previous six. A set of all-`None` states has size one. Two all-`None`
dicts compare equal. An empty result set satisfies *"all of them agreed"*. And *"no divergence found"*
is a GREEN wearing different words.

**Fix, and the part that matters.** Both were guarded — but fixing each site as it was found had
already failed six times, so the seventh fix is a test rather than a patch:
`tests/seed_spec.py::test_every_rig_touching_module_requires_evidence` audits every module in
`harness/`, and any module that drives the rig and forms a verdict without importing the guard fails
the suite. The eighth instance cannot be introduced silently.

**Why it mattered.** This one was found by deliberately asking *"where can a GREEN still mean nothing
happened?"* rather than by a run going wrong — which is the only reason it was found before someone
else found it. The principle this project keeps returning to is that **the evaluator must be harder to
fool than the system it evaluates**, and for six rounds the evaluator was not.

---

## 2026-08-23 — A false PASS from a plugin that did nothing at all

**Symptom.** `harness/confirm_range.py` ran the amount-integrity property against razorpay-woocommerce
**v4.0.0** and reported **GREEN** — apparently, that a nine-year-old release *did* check the amount,
contradicting a static screen that said the check has never existed.

**Cause.** v4.0.0 did nothing at all. A *matching* payment also left the order at `wc-pending` with an
empty queue: swapping plugin files does not reproduce a release's environment, because each version
activates its own database table and settings, and our rig built those for v4.8.7. The probe asked
"did an underpaid payment complete the order?", got "no", and returned GREEN. **"Nothing happened" was
scored as "the amount was checked."**

**Fix.** `amount_integrity.py` now runs a **control arm first** — a matching payment must complete the
order — and returns `UNDECIDABLE` when it does not, naming the likely cause. v4.0.0 and v4.7.0 both now
report UNDECIDABLE correctly.

**Why it mattered.** This is the **sixth** instance of one shape in this project, and it proves the
guard added earlier was incomplete: `measured.require()` had been wired into `check.py`, but
`amount_integrity.py` carried its own logic with no control. A guard applied to the place you happened
to be looking is not a guard.

**Consequence for what we publish.** The regression range ships as a claim about **source** across 111
releases, not about behaviour across them. Behaviour is confirmed only at the pinned version, and
`regression.py` says exactly that in its own output rather than in a footnote.

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
