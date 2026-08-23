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


def sql(query, timeout=120):
    """Read-only helper. -N -B gives tab-separated rows with no decoration."""
    rc, out, err = _run(["docker", "compose", "exec", "-T", "db", "mariadb",
                         "-uroot", "-proot", "--skip-ssl", "-N", "-B", "wordpress",
                         "-e", query], timeout=timeout)
    return out.strip()


def wp(*args, timeout=240):
    rc, out, err = _run(["docker", "compose", "run", "--rm", "-T", "cli", "wp"] + list(args),
                        timeout=timeout)
    return out.strip()


def new_order():
    """A virgin order plus its queue row. Returns (wc_order_id, rzp_order_id, paise)."""
    out = wp("eval-file", "/rig/new_order.php")
    kv = dict(l.split("=", 1) for l in out.splitlines() if "=" in l and not l.startswith(" "))
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
    return (p.stdout or "").strip()


def drain(wc_order):
    """Make any parked row eligible, then run the cron. Terminal state is only valid after this."""
    sql("UPDATE wp_rzp_webhook_requests SET rzp_webhook_notified_at=UNIX_TIMESTAMP()-600 "
        "WHERE order_id=%d AND rzp_update_order_cron_status=0;" % wc_order)
    wp("cron", "event", "run", "rzp_webhook_exec_cron")


def terminal_state(wc_order):
    """The merchant-visible outcome. This is what a shop owner would actually see."""
    status = sql("SELECT post_status FROM wp_posts WHERE ID=%d;" % wc_order)
    queue = sql("SELECT rzp_update_order_cron_status FROM wp_rzp_webhook_requests "
                "WHERE order_id=%d;" % wc_order)
    stored = sql("SELECT rzp_webhook_data FROM wp_rzp_webhook_requests WHERE order_id=%d;" % wc_order)
    try:
        events = [e.get("event") for e in json.loads(stored)] if stored else []
    except Exception:
        events = None
    return {"order_status": status or None,
            "queue_cron_status": queue or None,
            "stored_events": events}


def trial(sequence, drain_after_each=True, fault=False, underpay=False):
    """Run ONE delivery sequence against a fresh order. Pure record, no judgement."""
    wc, rzp, paise = new_order()
    log = []
    for step in sequence:
        code = deliver(step, wc, rzp, paise, fault=fault, underpay=underpay)
        log.append({"event": step, "http": code})
        if drain_after_each:
            drain(wc)
    drain(wc)  # always converge before reading
    return {"order": wc, "sequence": list(sequence), "fault_injected": bool(fault),
            "underpaid": bool(underpay), "deliveries": log, "terminal": terminal_state(wc)}
