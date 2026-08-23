"""
A verdict is only allowed if something was actually measured.

This module exists because of a defect found in this harness's own centrepiece on 2026-08-23:

    states = {t["terminal"]["order_status"] for t in trials}
    verdict = "GREEN" if len(states) == 1 else "RED"

If every trial returns order_status = None -- a dead rig, an order that was never created, a SQL
call that returned nothing -- then `states` is `{None}`, its length is 1, and the property reports
**GREEN**. The harness announces that the integration conforms, on the basis of having observed
nothing at all.

P2 and P5 had the same shape: comparing two all-None states finds them equal, and `None` is not in
the set of paid statuses, so both would also have passed.

That is the exact failure class this project exists to find, sitting in the tool that finds it. It is
also the third time the same shape has bitten here (see INCIDENTS.md: the false-negative CONVERGENT
run, the corpus rows that measured nothing, the vacuity checker that passed vacuously). The pattern
is always the same -- an absence of evidence being scored as evidence of absence -- so it is now a
shared, tested guard rather than a habit.

The rule: a property may not return a verdict unless every trial it relies on produced a
merchant-visible state that actually exists.
"""


class NotMeasured(RuntimeError):
    """Raised instead of returning a verdict when the evidence is missing."""


def require(trials, what="order_status"):
    """Assert that every trial observed something. Raise, loudly, if not.

    trials -- list of dicts as returned by rig.trial()
    what   -- the key inside trial["terminal"] that the property depends on
    """
    if not trials:
        raise NotMeasured(
            "no trials were run, so there is nothing to decide. A property with no evidence "
            "must not return a verdict.")

    missing = [t for t in trials if t.get("terminal", {}).get(what) in (None, "")]
    if missing:
        orders = ", ".join(str(t.get("order")) for t in missing[:5])
        raise NotMeasured(
            "%d of %d trials observed no %s (orders: %s).\n"
            "  The rig did not produce a merchant-visible state, so a GREEN here would mean\n"
            "  'we measured nothing', not 'the integration conforms'. Refusing to decide.\n"
            "  Usual causes: the rig is not running, the gateway plugin is not active, or the\n"
            "  order was never created. Try:  cd rig && ./setup.sh"
            % (len(missing), len(trials), what, orders))
    return True


def guard(fn):
    """Decorator form, for property checks that take (events, dry=False).

    Turns a NotMeasured into a verdict of UNMEASURED rather than an exception, so a single
    unmeasurable property does not abort the whole suite -- but it can never be mistaken for GREEN.
    """
    def wrapped(*a, **kw):
        try:
            return fn(*a, **kw)
        except NotMeasured as e:
            return {"property": getattr(fn, "property_key", fn.__name__),
                    "verdict": "UNMEASURED", "why": str(e)}
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    return wrapped
