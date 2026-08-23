"""
Mutual exclusion for rig runs.

Written after two schedule searches ran concurrently and silently corrupted each other: rig.drain()
invokes `wp cron event run`, and that cron drains EVERY eligible row in the table, not just the
caller's. Two runs therefore consume each other's parked events at arbitrary points and produce
terminal states that cannot be attributed to either sequence.

That is the same defect class this harness reports in razorpay-woocommerce -- concurrent consumers of
one shared queue with no mutual exclusion. Building it into the tool that finds it was instructive.

Usage:
    with runlock.exclusive("search"):
        ...
"""
import contextlib
import io
import os
import time

LOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rig", "out", ".rig.lock")


class RigBusy(RuntimeError):
    pass


@contextlib.contextmanager
def exclusive(who, stale_after=3600):
    path = os.path.abspath(LOCK)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        age = time.time() - os.path.getmtime(path)
        holder = io.open(path, encoding="utf-8").read().strip()
        if age < stale_after:
            raise RigBusy(
                "The rig is already in use by: %s (%.0fs ago).\n"
                "Concurrent runs corrupt each other -- the WordPress cron drains every eligible\n"
                "row, not just yours. Wait, or remove %s if you are certain it is stale."
                % (holder, age, path))
        print("  (removing a stale lock held by %s, %.0f min old)" % (holder, age / 60.0))
        os.remove(path)
    io.open(path, "w", encoding="utf-8").write("%s pid=%d" % (who, os.getpid()))
    try:
        yield
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
