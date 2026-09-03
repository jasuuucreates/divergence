"""
Driver for the razorpay-woocommerce rig.

One job: put a named event sequence into a live integration and read back the merchant-visible
terminal state. Everything above this layer (property checking, shrinking, reporting) is pure and
testable without Docker.

Design notes that matter:
  * Every trial gets a FRESH order. Reusing one order across trials leaks state between them and
    was the first thing that made an earlier hand-run experiment un-interpretable.
  * The terminal state is read only AFTER the deferred queue has drained. razorpay-woocommerce parks
    payment.authorized for a cron that only selects rows older than 300s, so a state read taken
    early measures the delay, not the behaviour.
  * Nothing here interprets the result. It records what happened. The oracle decides.
"""
import hashlib
import hmac
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RIG = os.path.join(os.path.dirname(HERE), "rig")

sys.path.insert(0, HERE)
import dockerenv  # noqa: E402

WEBHOOK_SECRET = "rig-webhook-secret-synthetic"
ENDPOINT = "http://localhost:8080/wp-admin/admin-post.php?action=rzp_wc_webhook"


def _env():
    """Docker is not on PATH on a default Windows install -- see harness/dockerenv.py."""
    return dockerenv.shell()


def _run(args, timeout=180):
    p = subprocess.run(args, cwd=RIG, env=_env(), capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "").replace("\r", ""), (p.stderr or "")


class RigFailure(RuntimeError):
    """The instrument failed. This is NOT the same fact as 'the query matched no rows'.

    Every guard above this layer tries to tell absence apart from failure. It could not, because
    this layer threw the distinction away: a dead database, a wrong password, a container that is
    not up, and a legitimately empty result set all returned the same empty string. An empty
    string then flows upward and reads as a conforming observation.
    """


def sql(query, timeout=120):
    """Read-only helper. -N -B gives tab-separated rows with no decoration.

    Raises RigFailure on a non-zero exit so that 'the database is down' can never be mistaken
    downstream for 'no rows matched'.
    """
    rc, out, err = _run(["docker", "compose", "exec", "-T", "db", "mariadb",
                         "-uroot", "-proot", "--skip-ssl", "-N", "-B", "wordpress",
                         "-e", query], timeout=timeout)
    if rc != 0:
        raise RigFailure("sql exited %d: %s\n  query: %s"
                         % (rc, (err or out).strip()[:400], query.strip()[:200]))
    return out.strip()


_WP_FAST = None      # None = not yet probed, True = exec path works, False = fall back


def wp(*args, **kw):
    """Run wp-cli.

    Two paths, and the difference matters for a live demonstration rather than for correctness:

      exec into the running wordpress container   ~1.4 s
      docker compose run --rm cli                 ~3.8 s

    `run --rm` creates and destroys a container per invocation. A single trial calls wp-cli twice
    (create the order, drain the cron), so the throwaway containers alone cost about 7.5 of the
    11.5 seconds a trial takes. That is the difference between a demo you can narrate and a demo
    with dead air in it.

    The fast path needs wp-cli inside the wordpress container, which rig/setup.sh installs. If it
    is absent -- an older rig, a partial setup -- this silently falls back rather than failing,
    because a slower correct answer beats a fast crash.
    """
    timeout = kw.pop("timeout", 240)
    allow_failure = kw.pop("allow_failure", False)
    if kw:
        raise TypeError("unexpected kwargs: %s" % sorted(kw))
    global _WP_FAST
    if _WP_FAST is None:
        rc, out, _ = _run(["docker", "compose", "exec", "-T", "-u", "33", "wordpress",
                           "wp", "--path=/var/www/html", "--version"], timeout=90)
        _WP_FAST = (rc == 0 and "WP-CLI" in out)
    if _WP_FAST:
        rc, out, err = _run(["docker", "compose", "exec", "-T", "-u", "33", "wordpress",
                             "wp", "--path=/var/www/html"] + list(args), timeout=timeout)
    else:
        rc, out, err = _run(["docker", "compose", "run", "--rm", "-T", "cli", "wp"] + list(args),
                            timeout=timeout)
    # Same rule as sql(): a wp-cli that could not run must not be indistinguishable from a wp-cli
    # that ran and found nothing. allow_failure is for the few callers that are legitimately
    # probing for absence and handle it themselves.
    if rc != 0 and not allow_failure:
        raise RigFailure("wp %s exited %d: %s"
                         % (" ".join(str(a) for a in args)[:120], rc, (err or out).strip()[:400]))
    return out.strip()


def new_order():
    """A virgin order plus its queue row. Returns (wc_order_id, rzp_order_id, paise).

    Fails with the CAUSE rather than a KeyError. new_order.php needs wc_create_order(), so it
    produces nothing at all when WooCommerce is not the active gateway -- which happens routinely,
    because only one gateway plugin can be active at a time and any EDD run leaves the other one
    switched off. That surfaced four separate times as `KeyError: 'ORDER_ID'`, which reads like a
    harness bug rather than the setup problem it is.
    """
    out = wp("eval-file", "/rig/new_order.php")
    kv = dict(l.split("=", 1) for l in out.splitlines() if "=" in l and not l.startswith(" "))
    if "ORDER_ID" not in kv:
        active = wp("plugin", "list", "--status=active", "--field=name")
        names = [l.strip() for l in active.splitlines()
                 if l.strip() and not l.startswith(("Warning", "["))]
        raise RuntimeError(
            "could not create a WooCommerce order, so there is nothing to measure. "
            "Active plugins: %s. "
            "This target needs both woocommerce and razorpay-woocommerce active; only one "
            "gateway plugin can be active at a time, so an earlier EDD run may have switched "
            "them off. Fix: cd rig && ./setup.sh  (or run harness/matrix.py, which activates "
            "the right target and verifies the switch took effect). new_order.php said: %r"
            % (", ".join(names) or "<none>", out[:200]))
    return int(kv["ORDER_ID"]), kv["RZP_ORDER_ID"], int(kv["PAISE"])


def build_event(event, wc_order, rzp_order, paise, payment_id=None, event_id=None,
                fault=False, underpay=False):
    """Serialise ONCE. The signature covers these exact bytes; re-serialising breaks it.

    fault=True mints a pay_FAULT... id, which makes the stub answer 500 -- the transient failure
    api.razorpay.com produces on a timeout or 5xx. The trigger lives in the payment id so it is
    visible in the transcript instead of hidden in configuration."""
    if payment_id is None:
        # The trigger class lives in the payment id so it is visible in the request transcript
        # rather than hidden in server configuration. See rig/stub/router.php.
        prefix = "pay_FAULT%010d" if fault else ("pay_UNDER%09d" if underpay else "pay_RIG%011d")
        payment_id = prefix % wc_order
    args = ["python", os.path.join(RIG, "make-webhook.py"),
            "--event", event, "--wc-order", str(wc_order), "--rzp-order", rzp_order,
            "--payment-id", payment_id, "--amount", str(paise),
            "--out", os.path.join(RIG, "out", "h_%s_%s.json" % (event.replace(".", "_"), wc_order))]
    subprocess.run(args, capture_output=True, text=True, timeout=90)
    path = args[-1]
    body = io.open(path, "rb").read()
    sig = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return path, sig


def deliver(event, wc_order, rzp_order, paise, event_id=None, fault=False, underpay=False):
    """POST one signed delivery. Returns the HTTP status the integration answered."""
    path, sig = build_event(event, wc_order, rzp_order, paise, fault=fault, underpay=underpay)
    hdrs = ["-H", "Content-Type: application/json", "-H", "X-Razorpay-Signature: " + sig]
    if event_id:
        # Razorpay sends this on every delivery; whether the integration reads it is P3.
        hdrs += ["-H", "X-Razorpay-Event-Id: " + event_id]
    p = subprocess.run(["curl", "-s", "-o", os.devnull, "-w", "%{http_code}", "-X", "POST",
                        ENDPOINT] + hdrs + ["--data-binary", "@" + path],
                       capture_output=True, text=True, timeout=120)
    code = (p.stdout or "").strip()
    # curl reports 000 when it received no response at all. P4 treated that as just another
    # non-2xx, so "the endpoint refused this event" and "the endpoint was never reached" arrived at
    # the oracle as the same fact -- and a stopped WordPress container therefore read as
    # conformance. An undelivered event is not a rejected event.
    if code in ("", "000"):
        raise RigFailure(
            "the webhook endpoint returned no response at all (curl code %r) for %s on order %s.\n"
            "  This is a DELIVERY failure, not a rejection, and must not be scored as one.\n"
            "  Usual cause: the wordpress container is not up.  Fix: cd rig && ./setup.sh"
            % (code, event, wc_order))
    return code


def _status_only(wc_order):
    return sql("SELECT post_status FROM wp_posts WHERE ID=%d;" % wc_order) or None


def drain(wc_order, verify=False, max_rounds=3):
    """Make any parked row eligible, run the cron, and -- when verify -- prove it stopped moving.

    verify is False for the drains BETWEEN deliveries, which only have to make progress, and True
    for the final drain before a state is read. It is the state we actually score that has to be
    proven converged; verifying every intermediate step doubles the cron work of a run and proves
    nothing extra, because nobody reads those states.

    Every verdict in this repo is taken on a converged state -- that is what makes "your cron would
    have fixed it later" unavailable as a rebuttal. That was a promise the code did not keep: drain
    ran the cron once and checked nothing, so a cron that silently did no work was indistinguishable
    from one that ran to completion, and the state was read whenever this happened to return.

    A fixpoint is the actual claim, so it is now the actual test: run the cron until two consecutive
    rounds observe the same merchant-visible status. If it never settles, refuse -- a state still in
    motion is not a terminal state and must not be scored as one.
    """
    sql("UPDATE wp_rzp_webhook_requests SET rzp_webhook_notified_at=UNIX_TIMESTAMP()-600 "
        "WHERE order_id=%d AND rzp_update_order_cron_status=0;" % wc_order)
    wp("cron", "event", "run", "rzp_webhook_exec_cron")
    if not verify:
        return None
    seen = _status_only(wc_order)
    settled = False
    for _ in range(max_rounds):
        sql("UPDATE wp_rzp_webhook_requests SET rzp_webhook_notified_at=UNIX_TIMESTAMP()-600 "
            "WHERE order_id=%d AND rzp_update_order_cron_status=0;" % wc_order)
        wp("cron", "event", "run", "rzp_webhook_exec_cron")
        again = _status_only(wc_order)
        if again == seen:
            settled = True
            break
        seen = again
    if not settled:
        raise RigFailure(
            "order %s never reached a fixpoint: the status was still changing after %d cron rounds "
            "(last observed %r). A state that is still moving is not a terminal state, and scoring "
            "it as one would measure the drain, not the integration."
            % (wc_order, max_rounds, seen))

    # A FIXPOINT IS NOT ENOUGH. A queue row that never started moving is also a fixpoint: the
    # status is stable at wc-pending forever, two consecutive rounds agree, and the check above is
    # satisfied by a drain that did absolutely nothing. redteam.py's `no-drain` attack found this
    # in the version of this function written earlier today -- with the cron neutralised, both
    # schedules sat at wc-pending with their rows still parked, both agreed, and P1 would have
    # reported GREEN. The headline RED becomes a GREEN because a cron did not fire.
    #
    # So also require that nothing is still WAITING to be processed. cron_status=0 means the row
    # is parked and unconsumed; if any remain after draining, the queue has not drained and the
    # state is not terminal, however stable it looks.
    parked = sql("SELECT COUNT(*) FROM wp_rzp_webhook_requests "
                 "WHERE order_id=%d AND rzp_update_order_cron_status=0;" % wc_order)
    if parked.strip() not in ("", "0"):
        raise RigFailure(
            "order %s still has %s unconsumed queue row(s) after %d cron rounds, so the deferred "
            "queue has NOT drained. The status is stable only because nothing ever ran. Reading "
            "this as a terminal state is how a dead cron turns a RED into a GREEN.\n"
            "  Usual cause: the cron hook is not registered (gateway plugin inactive or renamed)."
            % (wc_order, parked.strip(), max_rounds))
    return seen


def terminal_state(wc_order):
    """The merchant-visible outcome. This is what a shop owner would actually see.

    refund_count and refunded_total were added after the vacuity check showed P2 could not fail:
    order STATUS is the same whether an order was refunded once or twice, so a duplicate-tolerance
    property that only observes status is blind to double-refunding by construction. The property
    was not wrong; its observable was too coarse. WooCommerce stores each refund as its own
    shop_order_refund post whose parent is the order.
    """
    status = sql("SELECT post_status FROM wp_posts WHERE ID=%d;" % wc_order)
    refunds = sql("SELECT COUNT(*) FROM wp_posts WHERE post_parent=%d "
                  "AND post_type='shop_order_refund';" % wc_order)
    refunded = sql("SELECT COALESCE(SUM(CAST(meta_value AS DECIMAL(12,2))),0) FROM wp_postmeta m "
                   "JOIN wp_posts p ON p.ID=m.post_id "
                   "WHERE p.post_parent=%d AND p.post_type='shop_order_refund' "
                   "AND m.meta_key='_refund_amount';" % wc_order)
    queue = sql("SELECT rzp_update_order_cron_status FROM wp_rzp_webhook_requests "
                "WHERE order_id=%d;" % wc_order)
    stored = sql("SELECT rzp_webhook_data FROM wp_rzp_webhook_requests WHERE order_id=%d;" % wc_order)
    try:
        events = [e.get("event") for e in json.loads(stored)] if stored else []
    except Exception:
        events = None
    return {"order_status": status or None,
            "queue_cron_status": queue or None,
            "stored_events": events,
            "refund_count": int(refunds) if refunds.isdigit() else None,
            "refunded_total": refunded or None}


def trial(sequence, drain_after_each=True, fault=False, underpay=False):
    """Run ONE delivery sequence against a fresh order. Pure record, no judgement."""
    wc, rzp, paise = new_order()
    log = []
    for step in sequence:
        code = deliver(step, wc, rzp, paise, fault=fault, underpay=underpay)
        log.append({"event": step, "http": code})
        if drain_after_each:
            drain(wc)
    drain(wc, verify=True)  # always converge before reading -- and PROVE it converged
    return {"order": wc, "sequence": list(sequence), "fault_injected": bool(fault),
            "underpaid": bool(underpay), "deliveries": log, "terminal": terminal_state(wc)}
