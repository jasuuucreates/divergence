# Evidence index

Every file here is the output of a real run against the real rig. Nothing is illustrative.

This index exists because the claim it supports was, until 2026-09-04, **false**. `README.md` and
`LIMITATIONS.md` both stated that *"every transcript names the command that produced it"* — and not
one of the twenty files in this directory named a command. The claim was about this project's own
evidentiary discipline, which makes it the worst kind to get wrong. It is repaired here by writing
the mapping down.

The producer of each file was derived by searching the source for the filename rather than from
memory -- and the first pass searched only `harness/`, which produced a second wrong claim. Both
corrections are left visible below rather than smoothed over.

## Reproducible

| file | command | what it closes |
|---|---|---|
| `conformance_report.json` | `python harness/check.py` | the headline verdict: P1 RED, P2 GREEN, P4 RED, P5 RED, P3 YELLOW, OVERALL RED, exit 1 |
| `check_fault.log` | `python harness/check.py` (fault-injection arm) | behaviour when the stub returns 500 |
| `edd_probe.json` | `python harness/edd_probe.py` | the discrimination result — same property GREEN on a different plugin, with a passing control |
| `matrix.json` | `python harness/matrix.py` | both targets side by side, RED beside GREEN |
| `amount_integrity.json` | `python harness/amount_integrity.py` | the paisa-truncation analysis behind P5 |
| `causality.log` | `python harness/causality.py` | **the attempt that FAILED** — kept deliberately |
| `causality2.log` | `python harness/causality.py` | the attempt that succeeded: RED → patch → GREEN → restore → sha verified against a pre-patch value |
| `search.json`, `search_len2.log`, `search_len3.log` | `python harness/search.py` | exhaustive enumeration over the plugin's own event alphabet |
| `corpus.json` | `python harness/corpus.py` | the mutation corpus and confusion matrix (TP 5 / FN 0 / TN 3 / FP 0, n=8, P5 only) |
| `coverage.json` | `python harness/coverage.py` | which properties are exercised, and which are not |
| `vacuity.json` | `python harness/vacuity.py` | proof that each property *can* fail |
| `gated.json` | `python harness/gate.py` | the gated specification run |
| `stub_fidelity.json` | `python harness/stubcheck.py` | the stub matches the documented Payments entity |
| `regression.json` | `python harness/regression.py` | 111 of 139 released versions carry the defect |
| `regression_confirm.json` | `python harness/confirm_range.py` | the boundary of that range, re-confirmed |
| `demo.log` | `python harness/demo.py` | **the full 60-second live demo**, as a transcript, for anyone not running Docker |
| `redteam.log` | `python harness/redteam.py --destructive` | 11 live-rig attacks on our own instrument |
| `semgrep_woocommerce.json` | `semgrep --config=p/php rig/plugin/razorpay-woocommerce` | what a stock SAST tool finds on the plugin under test: 18 findings, none of them P1/P4/P5 |

## Also reproducible — from `evidence/scripts/`

These two are produced by committed scripts that live beside the transcripts rather than in
`harness/`. **This section is itself a correction.** The first version of this index declared both
files "orphaned" and "unreproducible", because the mapping was derived by searching `harness/*.py`
only — the search missed `evidence/scripts/` entirely. A wrong claim, published while repairing a
wrong claim, and caught the same way as everything else here: by checking instead of asserting.

| file | command | what it closes |
|---|---|---|
| `eventid_survey.json` | `python evidence/scripts/survey_eventid.py` | the **6 of 6** figure in README footnote 2 — no official Razorpay plugin references `x-razorpay-event-id`. Still **structural** evidence, so P3 stays capped at YELLOW; being reproducible does not promote it. |
| `money_truncation.json` | `python evidence/scripts/money_truncation.py` | the paisa-truncation arithmetic behind P5 |

`survey_plugins.py` and `survey_plugins2.py` are also here and produce `plugin_survey.json`, which
is **deliberately not published**: the two passes disagreed with each other, which made the result
unpublishable. `survey_eventid.py` exists because of that disagreement — it drops every semantic
pattern-match and tests the one thing grep can actually decide. The disagreement is recorded in
`INCIDENTS.md` ("Two of our own survey scripts disagreed with each other").

Both `harness/check.py` and `survey_eventid.py` previously pointed at `experiments/eventid_survey.json`,
a directory that does not exist in this repository. Corrected to `evidence/eventid_survey.json`.
`evidence/conformance_report.json` still carries the old string because it is a generated transcript;
it is rewritten on the next `python harness/check.py`.

## One edit made to these transcripts

`search_len2.log` and `search_len3.log` each contained one line printing the **absolute local path**
the run wrote to. That path named a private working directory, so both were rewritten to the
equivalent repository-relative path (`rig/out/search.json`) before publication. Same file, same run,
no number touched. It is recorded here because these are transcripts, and a transcript that has been
edited without saying so is not a transcript.

## Two files worth opening first

### `causality.log` — the failed arm, preserved
The harness does not assert which line is to blame. It patches the line, re-runs, and checks whether
the verdict moves. **The first attempt did not move it**, and the log says so in its own words:

```
P1 before patch : RED
P1 after  patch : RED
VERDICT: NOT CAUSAL. The verdict did not move when the blamed line changed.
         Either the diagnosis is wrong or the patch does not do what we think.
```

A tool that only publishes the run where its theory worked is not evidence, it is advertising.

### `redteam.log` — the instrument attacked on purpose
Eleven attacks against our own harness, including two that break the rig deliberately to check that
the guards actually fire. `no-drain` is the one to read: with the cron neutralised, `drain()` refuses
to return a state at all rather than handing back a stable-looking `wc-pending` that P1 would have
scored GREEN.
