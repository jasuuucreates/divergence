"""
tests/seed_spec.py -- the one file to read first.

Razorpay's own AI playbook (G.14) recommends a "seed spec": a single test that exercises every
convention in the test directory, so that a reader -- human or agent -- learns the shape of the whole
suite in one read instead of inferring it from partial overlap across many files.

This is that file. It covers every convention this repository uses:

  * pure logic is tested WITHOUT Docker, because a test that needs a container is a test nobody runs
  * the contract is data, so it can be asserted on directly
  * every property carries a fetched citation, and that is enforced here rather than trusted
  * expectations are registered BEFORE a run, and the registry is itself testable
  * verdict vocabulary is closed: GREEN / YELLOW / RED / DRY only

Run:  python -m pytest tests/ -q      (or: python tests/seed_spec.py)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "harness"))

import contract  # noqa: E402
import targets   # noqa: E402


# --- CONVENTION 1: the contract is data, and is assertable without running anything -----------

def test_every_property_has_a_citation():
    """A property without a source sentence is our opinion wearing a citation's clothes.

    This test exists because we once shipped a fabricated quotation in contract.py (see
    INCIDENTS.md, 2026-08-23). The rule is now enforced by the suite, not by discipline.
    """
    for p in contract.ALL_PROPERTIES:
        assert p.doc_quote and len(p.doc_quote) > 40, "%s has no real citation" % p.key
        assert p.doc_url.startswith("https://razorpay.com/"), \
            "%s cites a non-vendor source: %s" % (p.key, p.doc_url)
        assert p.rationale and len(p.rationale) > 80, "%s does not say why it follows" % p.key


def test_structural_properties_are_marked_as_such():
    """Structural checks read source; behavioural checks run it. Conflating them overstates evidence.

    P3 is decided by grepping for a header. Absence of the prescribed mechanism is NOT proof of
    non-idempotence -- an integration could de-duplicate some other way -- so P3 must never be
    allowed to return RED.
    """
    kinds = {p.key: p.verdict_kind for p in contract.ALL_PROPERTIES}
    assert kinds["P3-EVENT-ID-DEDUP"] == "structural"
    behavioural = [k for k, v in kinds.items() if v == "behavioural"]
    assert len(behavioural) >= 4, "most properties should be decided by execution, not by reading"


# --- CONVENTION 2: expectations are registered before a run, and are themselves testable -------

def test_expectations_are_registered_for_every_target():
    """A prediction written after the result is a rationalisation. targets.py holds them up front."""
    for t in targets.ALL.values():
        exp = targets.expectations(t)
        assert exp, "%s has no registered expectations" % t.key
        assert set(exp.values()) <= {"GREEN", "YELLOW", "RED"}, \
            "%s predicts a verdict outside the closed vocabulary" % t.key


def test_a_target_without_a_queue_cannot_fail_the_ordering_property():
    """Vacuous greens must be visible as vacuous.

    razorpay-edd dispatches one event and processes it synchronously, so P1 cannot fail there by
    construction. Reporting that as evidence of care would be dishonest, so the expectation registry
    derives it from structure and the README labels it n/a.
    """
    edd = targets.ALL["edd"]
    assert edd.defers_processing is False
    assert len(edd.events) == 1
    assert targets.expectations(edd)["P1-ORDER-INDEPENDENCE"] == "GREEN"

    woo = targets.ALL["woocommerce"]
    assert woo.defers_processing is True
    assert len(woo.events) > 1
    assert targets.expectations(woo)["P1-ORDER-INDEPENDENCE"] == "RED"


# --- CONVENTION 3: adapters make the per-target surface explicit and small ---------------------

def test_adapter_surface_is_complete_for_every_target():
    """Four fields vary per target and none is guessable from the others. A target missing any of
    them would fail in a way that reads as a finding rather than as a setup error."""
    for t in targets.ALL.values():
        assert t.endpoint_action, "%s: no endpoint" % t.key
        assert t.events, "%s: no event alphabet" % t.key
        assert len(t.order_notes_path) >= 4, "%s: no payload path to the order id" % t.key
        assert "%(order)d" in t.state_sql, "%s: state query is not parameterised" % t.key


def test_targets_disagree_on_the_payload_path():
    """The single most dangerous silent failure in this project.

    A WooCommerce-shaped body sent to EDD is dropped, the endpoint still answers 200, and the run
    looks exactly like a pass. Encoding the difference here means a future edit that unifies them
    breaks the suite instead of quietly producing false GREENs.
    """
    woo = targets.ALL["woocommerce"].order_notes_path
    edd = targets.ALL["edd"].order_notes_path
    assert woo != edd
    assert woo[1] == "payment" and woo[-1] == "woocommerce_order_id"
    assert edd[1] == "order" and edd[-1] == "edd_order_id"


# --- CONVENTION 4: a verdict is never returned without evidence -------------------------------

def test_a_verdict_requires_evidence():
    """The harness must refuse to decide when it observed nothing.

    This exists because check.py once computed `GREEN if len(states) == 1` over a set of terminal
    states that were all None -- a dead rig produced a set of size one, and the property announced
    that the integration conformed. Absence of evidence was being scored as evidence of absence.
    """
    import measured
    dead = [{"order": 1, "terminal": {"order_status": None}},
            {"order": 2, "terminal": {"order_status": None}}]
    try:
        measured.require(dead, "order_status")
        raise AssertionError("a dead rig was accepted as evidence")
    except measured.NotMeasured:
        pass
    assert measured.require([{"order": 1, "terminal": {"order_status": "wc-processing"}}],
                            "order_status")


def test_unmeasured_is_not_green():
    """UNMEASURED must outrank every other verdict in the summary.

    A run that could not observe the integration has neither cleared it nor condemned it, and must
    not be summarised as either."""
    import io as _io, os as _os, re as _re
    src = _io.open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                 "..", "harness", "check.py"), encoding="utf-8").read()
    assert 'overall = "UNMEASURED"' in src, "check.py does not surface UNMEASURED as an overall verdict"
    # and it must be decided BEFORE the GREEN branch
    assert src.index('overall = "UNMEASURED"') < src.index('else "GREEN")'),         "UNMEASURED must be decided before GREEN"


def test_every_rig_touching_module_requires_evidence():
    """No module that runs the rig may reach a verdict without asserting it measured something.

    This is an audit rather than a behaviour test, and it exists because the same defect has now
    appeared SEVEN times in this project under different disguises: a set of all-None states has
    size one, two all-None dicts compare equal, an empty result set satisfies "all of them agreed",
    and "no divergence found" is a GREEN wearing different words.

    Fixing each site as it was discovered did not stop the eighth. This test does: a new module that
    drives the rig and forms a verdict without importing the guard fails the suite.
    """
    import glob as _glob, io as _io, os as _os
    hdir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "harness")
    offenders = []
    for path in sorted(_glob.glob(_os.path.join(hdir, "*.py"))):
        name = _os.path.basename(path)
        src = _io.open(path, encoding="utf-8").read()
        drives_rig = ("rig.trial(" in src) or ("rig.terminal_state(" in src)
        forms_verdict = ('"GREEN"' in src) or ('"RED"' in src)
        if drives_rig and forms_verdict:
            guarded = ("measured.require" in src) or ("NotMeasured" in src) or ("UNDECIDABLE" in src)
            if not guarded:
                offenders.append(name)
    assert not offenders, (
        "these modules drive the rig and form a verdict without requiring evidence: %s. "
        "Import harness/measured.py and call require() before deciding." % ", ".join(offenders))


def test_disclosure_is_filed_before_publication():
    """The repository must not be publishable while the disclosure is unfiled.

    README.md once asserted that security-class findings had been reported privately. They had not
    -- the sentence was written while the disclosure was being planned and stayed after the plan
    slipped (INCIDENTS.md, 2026-08-24). That is a false claim about our own conduct, in the section
    a reviewer reads to judge whether we behaved responsibly.

    This test fails while the placeholders are unfilled. It is expected to FAIL until the disclosure
    is actually filed, and that is the point: a red test is a better guard than a good intention.
    """
    import io as _io, os as _os
    readme = _io.open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "README.md"),
                      encoding="utf-8").read()
    unfilled = [tok for tok in ("<DATE>", "<ID>", "<#N>", "NOT YET FILED") if tok in readme]
    assert not unfilled, (
        "the disclosure section still contains %s -- this repository must not be published "
        "until the security report is filed and the date/reference are recorded. "
        "See docs/14-DISCLOSURE.md in the war room for the drafts and the required sequencing "
        "(HackerOne first, then the public issue)." % ", ".join(unfilled))


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print("  PASS  %s" % name)
        except AssertionError as e:
            failures += 1
            print("  FAIL  %s -- %s" % (name, e))
    print("\n%d failed" % failures if failures else "\nall green")
    sys.exit(1 if failures else 0)
