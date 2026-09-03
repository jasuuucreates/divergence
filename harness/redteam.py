#!/usr/bin/env python
"""
harness/redteam.py -- the attacks that need a live rig.

tests/adversarial.py attacks the harness's SOURCE and runs in two seconds. This attacks the
harness's BEHAVIOUR, and needs Docker. Split that way because a test needing a container is a test
nobody runs before committing, and half the defects here were committed at 3am.

THE QUESTION IS ALWAYS THE SAME: can this harness be made to report GREEN when it has not earned it?
So every attack below states three things, and prints all three whether it passes or fails:

    ATTACKS            what part of the instrument is under attack
    EXPECT             the correct behaviour -- almost always "refuse to decide", not "pass"
    WRONG LOOKS LIKE   the specific output that would mean we have a false GREEN

Two attack classes:

    INSTRUMENT   break the rig on purpose (kill the database, deactivate the plugin, neutralise the
                 cron) and require the harness to REFUSE rather than to report. A GREEN here is the
                 worst possible result: it means every published verdict is unfalsifiable.

    INTEGRATION  send the plugin things Razorpay could really send (empty body, truncated body,
                 valid signature addressed to an order that does not exist, the same event id
                 twice, 12 MB, two deliveries at once). A finding here would be a NEW finding about
                 razorpay-woocommerce, and must not be claimed until it has actually been run.

STATUS, STATED PLAINLY: as of 2026-09-04 this file has been WRITTEN AND REVIEWED BUT NOT EXECUTED.
Nothing in it may be quoted as a result until it has been. The instrument attacks predict FAILURE
for the reasons tests/adversarial.py already demonstrates from source; the integration attacks
predict nothing, because guessing an outcome and then finding it is how the investigator's
contaminated metric happened.

    python harness/redteam.py --list                 # the plan, with ranks. Costs nothing.
    python harness/redteam.py --only sig unknown-order malformed
    python harness/redteam.py --destructive          # includes the attacks that break the rig
"""
import argparse
import hashlib
import hmac
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RIG = os.path.join(ROOT, "rig")

sys.path.insert(0, HERE)
import dockerenv  # noqa: E402
import rig        # noqa: E402
import runlock    # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PAID = ("wc-processing", "wc-completed")
ATTACKS = []


def attack(key, rank, attacks, expect, wrong, destructive=False):
    def deco(fn):
        ATTACKS.append({"key": key, "rank": rank, "attacks": attacks, "expect": expect,
                        "wrong": wrong, "destructive": destructive, "fn": fn})
        return fn
    return deco


# -------------------------------------------------------------------------------------------------
# raw delivery: sign EXACTLY the bytes we send, so a malformed body still carries a valid signature.
# That is the interesting case. An attacker cannot forge a signature, but Razorpay itself can
# legitimately deliver a body this integration fails to parse -- a truncated response, a field the
# integration does not expect -- and the signature on those bytes is genuine.
# -------------------------------------------------------------------------------------------------
def post_raw(body_bytes, sign=True, corrupt_signature=False, event_id=None, headers=()):
    path = os.path.join(RIG, "out", "redteam_body.bin")
    io.open(path, "wb").write(body_bytes)
    sig = hmac.new(rig.WEBHOOK_SECRET.encode(), body_bytes, hashlib.sha256).hexdigest()
    if corrupt_signature:
        sig = ("0" if sig[0] != "0" else "1") + sig[1:]
    hdrs = ["-H", "Content-Type: application/json"]
    if sign:
        hdrs += ["-H", "X-Razorpay-Signature: " + sig]
    if event_id:
        hdrs += ["-H", "X-Razorpay-Event-Id: " + event_id]
    for h in headers:
        hdrs += ["-H", h]
    p = subprocess.run(["curl", "-s", "-o", os.devnull, "-w", "%{http_code}", "--max-time", "30",
                        "-X", "POST", rig.ENDPOINT] + hdrs + ["--data-binary", "@" + path],
                       capture_output=True, text=True, timeout=90)
    return (p.stdout or "").strip()


def signed_body(wc_order, rzp_order, paise, event="payment.authorized", mutate=None):
    """Build the canonical body the rig would send, then hand it to `mutate` for corruption."""
    path, _ = rig.build_event(event, wc_order, rzp_order, paise)
    raw = io.open(path, "rb").read()
    return mutate(raw) if mutate else raw


def fresh():
    return rig.new_order()


def state(wc):
    rig.drain(wc)
    return rig.terminal_state(wc)


def untouched(st):
    """The order did not move AND the queue row was not claimed."""
    return st["order_status"] in (None, "wc-pending") and st["queue_cron_status"] != "2"


def silently_lost(st):
    """THE defect shape these body attacks hunt: responsibility taken, nothing done.

    The endpoint answered 2xx and claimed the queue row (cron_status=2), so Razorpay will never
    retry the event -- and yet the order never left pending, so nothing was actually done with it.
    That is P4 NO-SILENT-LOSS.

    Its complement is NOT "the order is untouched". An event that was accepted and fully PROCESSED
    -- order moved to a real state, queue row consumed -- is responsibility taken AND discharged,
    which is correct behaviour. `untouched()` alone scored that as a failure, which is how the
    oversize attack accused razorpay-woocommerce of a defect for handling a 12 MB body correctly.
    Scoring correct code as RED is a documented incident in this project (2026-08-23); doing it to
    the vendor rather than to ourselves would be worse, because it is the accusation we publish.
    """
    return st["queue_cron_status"] == "2" and st["order_status"] in (None, "wc-pending")


# =================================================================================================
# CONTROL. Nothing below is trustworthy until this passes. Fail-closed, always first.
# =================================================================================================

@attack("control", 0,
        "the whole instrument: plugin active, endpoint routed, stub reachable, signing correct, "
        "notes addressing correct, cron draining",
        "a correctly-signed, correctly-addressed, amount-matching payment.authorized moves a fresh "
        "order from wc-pending to wc-processing",
        "if this fails, EVERY other line in this run is meaningless -- a dead plugin makes every "
        "attack below 'pass' by doing nothing, which is precisely the false GREEN we are hunting")
def a_control():
    wc, rzp, paise = fresh()
    code = rig.deliver("payment.authorized", wc, rzp, paise)
    st = state(wc)
    ok = st["order_status"] in PAID
    return ok, "HTTP %s -> %s (queue=%s)" % (code, st["order_status"], st["queue_cron_status"])


# =================================================================================================
# INSTRUMENT ATTACKS -- break the rig and require a REFUSAL
# =================================================================================================

@attack("sig", 0,
        "the assumption that our deliveries are being accepted at all",
        "a body whose signature is corrupted by one character must be REJECTED (non-2xx) and must "
        "leave the order untouched -- and the identical body with a correct signature must move it",
        "if the corrupted body is accepted, the plugin is not verifying signatures and P1/P2/P4/P5 "
        "were measured through an unauthenticated door. If BOTH bodies are rejected, our secret has "
        "drifted from the plugin's and every RED in this repository was measured on a dead endpoint")
def a_signature_mismatch():
    wc, rzp, paise = fresh()
    bad = post_raw(signed_body(wc, rzp, paise), corrupt_signature=True)
    st_bad = state(wc)
    wc2, rzp2, paise2 = fresh()
    good = post_raw(signed_body(wc2, rzp2, paise2))
    st_good = state(wc2)
    ok = untouched(st_bad) and st_good["order_status"] in PAID
    return ok, "corrupted -> HTTP %s %s | correct -> HTTP %s %s" % (
        bad, st_bad["order_status"], good, st_good["order_status"])


@attack("unknown-order", 0,
        "the addressing channel. razorpay-woocommerce reads the target from "
        "payload.payment.entity.notes.woocommerce_order_id; razorpay-edd reads a DIFFERENT entity "
        "and a DIFFERENT key. A body addressed wrongly is dropped and the endpoint still answers "
        "2xx -- which is indistinguishable from a pass",
        "a validly-signed body naming order 999999999 must leave the order under test untouched, "
        "and the harness must be able to tell that delivery apart from a correct one",
        "if a misaddressed delivery is indistinguishable from a correct one, then a plugin update "
        "that renames the notes key silently converts every RED in this repository into a GREEN, "
        "and nothing in the harness would notice. This is the razorpay-edd payload-shape hazard, "
        "unguarded on the primary target")
def a_unknown_order():
    wc, rzp, paise = fresh()
    raw = signed_body(wc, rzp, paise)
    doc = json.loads(raw)
    doc["payload"]["payment"]["entity"]["notes"]["woocommerce_order_id"] = "999999999"
    code = post_raw(json.dumps(doc, separators=(",", ":")).encode())
    st = state(wc)
    return untouched(st), "HTTP %s -> %s (queue=%s)" % (code, st["order_status"],
                                                        st["queue_cron_status"])


@attack("malformed", 1,
        "the integration's parser, and P4's ability to notice a body that was accepted and dropped",
        "an empty body, a truncated body, a lone '{', and a valid-JSON-wrong-schema body must each "
        "either be refused (non-2xx) or accepted without claiming the queue row. Note the signature "
        "is VALID on each -- it is computed over the exact bytes sent, which is what Razorpay would "
        "genuinely produce if a response were truncated in flight",
        "HTTP 2xx together with queue_cron_status=2 and an order still at wc-pending is a NEW "
        "instance of P4 NO-SILENT-LOSS: the endpoint told Razorpay it took responsibility for an "
        "event it could not even parse, so Razorpay will never retry it")
def a_malformed_bodies():
    rows, ok = [], True
    canonical = None
    cases = [
        ("empty", lambda r: b""),
        ("open-brace", lambda r: b"{"),
        ("truncated-50pc", lambda r: r[:len(r) // 2]),
        ("null-payload", lambda r: json.dumps({"entity": "event", "event": "payment.authorized",
                                               "payload": None}).encode()),
        ("wrong-schema", lambda r: json.dumps({"hello": "world"}).encode()),
        ("nul-bytes", lambda r: r[:20] + b"\x00\x00" + r[20:]),
    ]
    for name, mut in cases:
        wc, rzp, paise = fresh()
        if canonical is None:
            canonical = signed_body(wc, rzp, paise)
        code = post_raw(mut(signed_body(wc, rzp, paise)))
        st = state(wc)
        good = untouched(st)
        ok = ok and good
        rows.append("%s: HTTP %s %s q=%s%s" % (name, code, st["order_status"],
                                               st["queue_cron_status"], "" if good else "  <-- !!"))
    return ok, " | ".join(rows)


@attack("oversize", 2,
        "PHP's post_max_size (8M by default) and the endpoint's behaviour when the body it is "
        "asked to verify was silently discarded before the handler ran",
        "a 12 MB validly-signed body must be refused, or accepted without claiming the queue row",
        "2xx plus a claimed queue row: the same silent-loss shape as the malformed cases, reached "
        "by a route no signature check can see, because PHP drops the body before any userland code")
def a_oversize():
    wc, rzp, paise = fresh()
    raw = signed_body(wc, rzp, paise)
    doc = json.loads(raw)
    doc["payload"]["payment"]["entity"]["description"] = "A" * (12 * 1024 * 1024)
    code = post_raw(json.dumps(doc, separators=(",", ":")).encode())
    st = state(wc)
    # Three outcomes are conformant: refused; accepted without claiming the row; or accepted and
    # actually processed. Only "claimed the row and left the order pending" is the silent loss.
    return (not silently_lost(st)), "12MB -> HTTP %s -> %s (queue=%s)" % (
        code, st["order_status"], st["queue_cron_status"])


@attack("event-id", 1,
        "P3. It is demoted to structural/YELLOW on the strength of a grep: the plugin never "
        "mentions x-razorpay-event-id. That is an argument from source, and this repository's "
        "whole thesis is that you execute instead of arguing",
        "redelivering the same event twice with the SAME X-Razorpay-Event-Id must produce exactly "
        "the same terminal state as redelivering it with two DIFFERENT event ids -- because the "
        "plugin does not read the header, the header cannot matter",
        "if the two runs differ, the plugin DOES consume the header somewhere and P3's structural "
        "claim is wrong in our published contract. If they agree, P3 stops being a grep result and "
        "becomes a behavioural one, which is a strict upgrade to the weakest property we ship. "
        "Note the rig currently never sends this header at all, so P2's GREEN was measured without "
        "the mechanism Razorpay prescribes even being present")
def a_event_id():
    wc, rzp, paise = fresh()
    body = signed_body(wc, rzp, paise)
    post_raw(body, event_id="evt_REDTEAM_SAME")
    post_raw(body, event_id="evt_REDTEAM_SAME")
    same = state(wc)
    wc2, rzp2, paise2 = fresh()
    body2 = signed_body(wc2, rzp2, paise2)
    post_raw(body2, event_id="evt_REDTEAM_A")
    post_raw(body2, event_id="evt_REDTEAM_B")
    diff = state(wc2)
    keys = ("order_status", "refund_count", "refunded_total", "queue_cron_status")
    a = {k: same.get(k) for k in keys}
    b = {k: diff.get(k) for k in keys}
    return a == b, "same-id %s | distinct-ids %s" % (a, b)


@attack("concurrent", 1,
        "a defect class this harness diagnosed IN ITSELF and never tested for in the plugin. "
        "harness/runlock.py exists because two searches drained each other's queue rows, and its "
        "own docstring says: 'That is the same defect class this harness reports in "
        "razorpay-woocommerce -- concurrent consumers of one shared queue with no mutual "
        "exclusion.' We built the mitigation into our tool and never sent the plugin the input",
        "two simultaneous payment.authorized deliveries for one order must leave the same terminal "
        "state as one delivery -- the second is a duplicate, and P2 says duplicates are legal input",
        "a doubled refund count, two stored events, or a queue row claimed twice would be a new "
        "behavioural finding. A judge who reads runlock.py WILL ask why we never sent it")
def a_concurrent():
    wc, rzp, paise = fresh()
    body = signed_body(wc, rzp, paise)
    path = os.path.join(RIG, "out", "redteam_conc.bin")
    io.open(path, "wb").write(body)
    sig = hmac.new(rig.WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    cmd = ["curl", "-s", "-o", os.devnull, "-w", "%{http_code}\n", "-X", "POST", rig.ENDPOINT,
           "-H", "Content-Type: application/json", "-H", "X-Razorpay-Signature: " + sig,
           "--data-binary", "@" + path]
    procs = [subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True) for _ in range(2)]
    codes = [p.communicate()[0].strip() for p in procs]
    conc = state(wc)
    wc2, rzp2, paise2 = fresh()
    rig.deliver("payment.authorized", wc2, rzp2, paise2)
    seq = state(wc2)
    keys = ("order_status", "refund_count", "refunded_total")
    a = {k: conc.get(k) for k in keys}
    b = {k: seq.get(k) for k in keys}
    return a == b, "concurrent(HTTP %s) %s | sequential %s" % (",".join(codes), a, b)


@attack("real-clock", 1,
        "the honesty of every P1 result. rig.drain() BACKDATES rzp_webhook_notified_at to "
        "UNIX_TIMESTAMP()-600 so the >=300s cron window opens immediately. A judge is entitled to "
        "say: you falsified the clock, and the real system converges on its own",
        "one trial run with NO backdating, waiting the real 320 seconds, must reach exactly the "
        "terminal state the backdated trial reaches",
        "if they differ, the P1 RED is an artefact of our clock manipulation and the headline "
        "finding is not a finding. Costs ~6 minutes, run ONCE, and the transcript permanently "
        "closes the strongest available objection to the centrepiece")
def a_real_clock():
    wc, rzp, paise = fresh()
    rig.deliver("payment.authorized", wc, rzp, paise)
    rig.deliver("refund.created", wc, rzp, paise)
    print("      waiting 320s for the plugin's own 300s window -- no backdating ...")
    time.sleep(320)
    rig.wp("cron", "event", "run", "rzp_webhook_exec_cron")
    real = rig.terminal_state(wc)
    wc2, rzp2, paise2 = fresh()
    for e in ("payment.authorized", "refund.created"):
        rig.deliver(e, wc2, rzp2, paise2)
    backdated = state(wc2)
    ok = real["order_status"] == backdated["order_status"]
    return ok, "real clock -> %s | backdated -> %s" % (real["order_status"],
                                                       backdated["order_status"])


# =================================================================================================
# DESTRUCTIVE. Each breaks the rig on purpose and restores it. Opt in with --destructive.
# The correct outcome for all three is that check.py REFUSES. A GREEN is the catastrophic result.
# =================================================================================================
def _compose(*args):
    return subprocess.run(["docker", "compose"] + list(args), cwd=RIG, env=dockerenv.shell(),
                          capture_output=True, text=True, timeout=300)


def _run_check():
    """Run check.py under attack and classify how it declined to answer.

    `overall` is normalised to "UNMEASURED" when check.py ABORTED rather than printing a verdict
    table. Both destructive attacks state their expectation as "OVERALL=UNMEASURED, OR AN ABORT",
    and check.py's control arm implements the abort: it raises SystemExit("REFUSING TO RUN ...")
    and never reaches the OVERALL line. The first version of this helper only recognised the
    literal string, so a harness that refused CORRECTLY - by aborting, with zero GREENs - was
    scored as BROKEN. That is a false accusation against our own tool, produced by a criterion
    that did not implement its own stated expectation. Same defect class as the three first-draft
    adversarial tests that passed on prose; see INCIDENTS.md 2026-09-04.
    """
    p = subprocess.run([sys.executable, "-u", os.path.join(HERE, "check.py")],
                       capture_output=True, text=True, timeout=3600)
    out = (p.stdout or "") + (p.stderr or "")
    overall = "?"
    for line in out.splitlines():
        if line.startswith("OVERALL:"):
            overall = line.split()[1]
    greens = [l.strip() for l in out.splitlines()
              if l.strip().startswith("P") and l.strip().endswith("GREEN")]
    # An abort counts as UNMEASURED only if it really produced no verdict: non-zero exit, no
    # OVERALL line, and nothing reported GREEN. A crash that still printed a GREEN is NOT a refusal.
    aborted = (p.returncode != 0 and overall == "?" and not greens)
    if aborted:
        overall = "UNMEASURED"
    return overall, greens, out


@attack("plugin-off", 0,
        "the exact incident of 2026-09-04, moved to the primary target. Deactivate "
        "razorpay-woocommerce and LEAVE woocommerce active: orders still create, the endpoint is "
        "dead, every schedule leaves the order at wc-pending. measured.require() passes, because "
        "wc-pending is a real value -- the guard stops 'we measured nothing', not 'we measured "
        "nothing happening'",
        "check.py must refuse: OVERALL=UNMEASURED, or an abort. No property may report GREEN",
        "any GREEN here means the centrepiece clears razorpay-woocommerce on the strength of "
        "razorpay-woocommerce being switched off. Predicted P1=GREEN P2=GREEN P5=GREEN today",
        destructive=True)
def a_plugin_off():
    _compose("run", "--rm", "-T", "cli", "wp", "plugin", "deactivate", "razorpay-woocommerce")
    try:
        overall, greens, _ = _run_check()
    finally:
        _compose("run", "--rm", "-T", "cli", "wp", "plugin", "activate", "woocommerce")
        _compose("run", "--rm", "-T", "cli", "wp", "plugin", "activate", "razorpay-woocommerce")
    return (overall == "UNMEASURED" and not greens), "OVERALL=%s greens=%s" % (overall, greens)


def _db_reachable():
    """True if the harness can actually read the database right now."""
    try:
        rig.sql("SELECT 1;")
        return True
    except Exception:
        return False


@attack("db-down", 1,
        "every SQL read. rig.sql() discards the return code, so a dead database and an empty "
        "result set are the same empty string",
        "check.py must report UNMEASURED (measured.require should catch the all-None states); "
        "search.py must NOT print 'No divergence found ... that is a real result'",
        "check.py is expected to hold here -- this is what measured.py was built for. search.py is "
        "expected to FAIL, because it drives the rig, forms a verdict in different words, and "
        "imports the guard without calling it",
        destructive=True)
def a_db_down():
    """Stop the database and require the harness to refuse.

    THIS ATTACK NEEDS ITS OWN CONTROL ARM, and the first version did not have one. rig/docker-
    compose.yml declares `cli: depends_on: db: condition: service_healthy`, so the harness's own
    wp-cli fallback path (`docker compose run --rm cli`) STARTS THE DATABASE and waits for it to be
    healthy. The database was therefore back up within seconds of being stopped, check.py ran
    against a perfectly healthy rig, and the attack reported BROKEN on the strength of a verdict
    table full of real data -- an experiment that never ran under the condition it was named for,
    reported as a defect. That is the same shape as every other finding recorded today, applied to
    the instrument rather than to the subject.

    So: assert the precondition after the run. If the database came back, the result is
    UNDECIDABLE, not a pass and not a failure.
    """
    _compose("stop", "db")
    if _db_reachable():
        _compose("start", "db")
        time.sleep(25)
        return None, ("PRECONDITION NOT HELD: the database was reachable immediately after being "
                      "stopped (docker-compose `cli` depends_on db: service_healthy restarts it). "
                      "This attack cannot be run against the current compose topology.")
    try:
        overall, greens, _ = _run_check()
        came_back = _db_reachable()
    finally:
        _compose("start", "db")
        time.sleep(25)
    if came_back:
        return None, ("PRECONDITION LOST MID-RUN: the database was restarted by the harness's own "
                      "wp-cli path during the run, so check.py measured a healthy rig. "
                      "OVERALL=%s greens=%s -- but this says nothing about db-down behaviour."
                      % (overall, greens))
    return (overall == "UNMEASURED" and not greens), "OVERALL=%s greens=%s" % (overall, greens)


@attack("no-drain", 0,
        "the promise in rig.py's docstring: 'The terminal state is read only AFTER the deferred "
        "queue has drained.' drain() runs the cron and discards the result, so a renamed hook, a "
        "deactivated gateway or a WP-CLI error makes it a silent no-op",
        "with the cron neutralised, check.py must refuse. It must not read a pre-convergence state "
        "and call it terminal",
        "P1=GREEN is the predicted failure: nothing ever leaves wc-pending, every schedule agrees, "
        "and the headline RED becomes a GREEN because a cron did not fire. This is the single "
        "cheapest way to make the centrepiece lie",
        destructive=True)
def a_no_drain():
    # NEUTRALISE THE CRON, NOT THE FUNCTION. The first version of this attack replaced drain()
    # itself with a no-op lambda. That is a stronger adversary than the real world and, worse, it
    # is unfalsifiable: with the whole function gone, no guard inside drain() can ever fire, so the
    # attack could never be closed by fixing drain(). The actual hazard named in this attack's own
    # description is "a renamed hook, a deactivated gateway or a WP-CLI error makes it a silent
    # no-op" -- the function RUNS and achieves nothing. So stub the cron invocation and leave
    # drain's own verification live. If drain cannot tell that nothing drained, that is the finding.
    original_wp = rig.wp

    def _no_cron(*args, **kw):
        if args and args[0] == "cron":
            return ""          # the cron command "succeeds" and does nothing
        return original_wp(*args, **kw)

    rig.wp = _no_cron
    try:
        trials = [rig.trial(["payment.authorized", "refund.created"]),
                  rig.trial(["refund.created", "payment.authorized"])]
    except rig.RigFailure as e:
        # Refusing IS the correct behaviour: drain noticed the queue had not drained and declined
        # to hand back a state. Report the refusal as a HELD result rather than an error.
        rig.wp = original_wp
        return True, "drain REFUSED to return a state: %s" % str(e).splitlines()[0][:150]
    finally:
        rig.wp = original_wp
    states = {t["terminal"]["order_status"] for t in trials}
    # The harness would call len(states) == 1 a GREEN. Correct behaviour is to refuse, because
    # nothing has converged. We detect the hazard by checking whether any row is still parked.
    parked = [t for t in trials if t["terminal"]["queue_cron_status"] == "0"]
    return not (len(states) == 1 and parked), \
        "states=%s parked_rows=%d  (a single state over parked rows is a false GREEN)" % (
            sorted(x for x in states if x), len(parked))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--destructive", action="store_true")
    a = ap.parse_args()

    plan = [x for x in ATTACKS if not a.only or x["key"] in a.only]
    if not a.destructive:
        plan = [x for x in plan if not x["destructive"]]
    plan.sort(key=lambda x: (x["key"] != "control", x["rank"], x["key"]))

    print("=" * 100)
    print("RED TEAM -- can this harness be made to report a GREEN it has not earned?")
    print("=" * 100)
    for x in plan:
        print("\n  %-14s [rank %d]%s" % (x["key"], x["rank"], "  DESTRUCTIVE" if x["destructive"] else ""))
        print("     ATTACKS   %s" % x["attacks"])
        print("     EXPECT    %s" % x["expect"])
        print("     WRONG     %s" % x["wrong"])
    if a.list:
        print("\n%d attacks planned. --list only; nothing was run." % len(plan))
        return 0

    print("\n" + "=" * 100)
    rows, failed, undecidable = [], 0, 0
    for x in plan:
        print("\n  RUNNING %s ..." % x["key"])
        try:
            ok, detail = x["fn"]()
        except Exception as e:                                   # noqa: BLE001
            ok, detail = "ERROR", "%s: %s" % (type(e).__name__, e)
        # Three outcomes, not two. `None` means the attack could not establish its own
        # precondition, so it measured nothing. That is UNDECIDABLE. Counting it as BROKEN would
        # be an unearned finding about our own harness, in exactly the way this file exists to
        # prevent -- and it is what the db-down attack did before it was given a control arm.
        label = {True: "HELD  ", False: "BROKEN", None: "UNDECIDABLE", "ERROR": "ERROR "}[ok]
        rows.append({"key": x["key"], "rank": x["rank"], "ok": ok, "detail": detail,
                     "attacks": x["attacks"], "expect": x["expect"], "wrong": x["wrong"]})
        print("     %s   %s" % (label, detail))
        # Count BEFORE the control-arm break. Breaking first meant a failed control printed
        # "0 of 1 attacks BROKE the harness" -- a summary line that contradicted the BROKEN it had
        # just printed two lines above.
        if ok is None:
            undecidable += 1
        elif ok is not True:
            failed += 1
        if x["key"] == "control" and ok is not True:
            print("\n  CONTROL FAILED -- nothing below would be trustworthy. Refusing to continue.")
            print("  Fix the rig first:  cd rig && ./setup.sh")
            break

    print("\n" + "=" * 100)
    print("%d of %d attacks BROKE the harness.%s"
          % (failed, len(rows),
             "   (%d UNDECIDABLE -- precondition not established)" % undecidable
             if undecidable else ""))
    print("A broken attack is a route to a GREEN we have not earned. Each one is a finding about")
    print("this harness, not about Razorpay, and belongs in INCIDENTS.md.")
    print("=" * 100)
    out = os.path.join(RIG, "out", "redteam.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    io.open(out, "w", encoding="utf-8").write(json.dumps(rows, indent=2))
    print("saved -> %s" % os.path.relpath(out, ROOT))
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        with runlock.exclusive("redteam"):
            sys.exit(main())
    except runlock.RigBusy as e:
        print("REFUSING TO START.")
        print(e)
        sys.exit(2)
