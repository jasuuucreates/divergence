"""
Target adapters.

Up to now the driver was hard-wired to razorpay-woocommerce, which made the whole thing a WooCommerce
script with a contract bolted on. A conformance harness has to be able to point at an integration it
was not written for, or the word "harness" is doing no work.

An adapter is the minimum a new target needs. Deriving it for razorpay-edd showed that four things
vary independently, and none of them is guessable from the others:

  1. ENDPOINT        WooCommerce: admin-post.php?action=rzp_wc_webhook
                     EDD:         admin-post.php?action=rzp_edd_webhook
  2. EVENT ALPHABET  WooCommerce dispatches 8 events; EDD dispatches exactly one, `order.paid`.
                     Sending an event a target does not dispatch measures nothing about the target.
  3. PAYLOAD SHAPE   WooCommerce reads payload.payment.entity.notes.woocommerce_order_id
                     EDD reads      payload.order.entity.notes.edd_order_id
                     Different entity, different notes key. A payload built for one is silently
                     DROPPED by the other -- which would look exactly like a passing test.
  4. STATE QUERY     what "the merchant-visible terminal state" means in that target's schema.

The signature scheme happens to be identical (HMAC-SHA256 over the raw body, X-Razorpay-Signature),
so it is not yet an adapter axis. It is left explicit rather than assumed, because the first target
that differs would otherwise fail in a way that reads as a finding.

WHY THIS MATTERS FOR THE SUBMISSION: razorpay-edd is BETTER code than razorpay-woocommerce -- it
compares the paid amount to the order amount (includes/razorpay-webhook.php:130) and it processes
synchronously with no deferred queue. So the harness should report GREEN there where WooCommerce is
RED. A harness that reports RED everywhere is a bug list. The GREEN is the deliverable.
"""


class Target:
    def __init__(self, key, repo, ref, plugin_slug, endpoint_action, events,
                 order_notes_path, state_sql, seed_php, notes,
                 defers_processing, verifies_amount_at):
        self.key = key
        self.repo = repo
        self.ref = ref
        self.plugin_slug = plugin_slug
        self.endpoint_action = endpoint_action
        self.events = events                    # only what the target's own switch dispatches
        self.order_notes_path = order_notes_path
        self.state_sql = state_sql
        self.seed_php = seed_php
        self.notes = notes
        # Recorded so the report can say what we EXPECT before it says what we found.
        # An expectation stated in advance is the difference between a prediction and a rationalisation.
        self.defers_processing = defers_processing
        self.verifies_amount_at = verifies_amount_at

    def endpoint(self, base="http://localhost:8080"):
        return "%s/wp-admin/admin-post.php?action=%s" % (base, self.endpoint_action)

    def __repr__(self):
        return "<Target %s>" % self.key


WOOCOMMERCE = Target(
    key="woocommerce",
    repo="razorpay/razorpay-woocommerce",
    ref="v4.8.7",
    plugin_slug="razorpay-woocommerce",
    endpoint_action="rzp_wc_webhook",
    events=["payment.authorized", "payment.failed", "payment.pending", "refund.created"],
    order_notes_path=("payload", "payment", "entity", "notes", "woocommerce_order_id"),
    state_sql="SELECT post_status FROM wp_posts WHERE ID=%(order)d;",
    seed_php="/rig/new_order.php",
    notes="Defers payment.authorized to a 300s cron; every other event is synchronous.",
    defers_processing=True,
    verifies_amount_at=None,        # absent from paymentAuthorized(); present only on the VA path
)

EDD = Target(
    key="edd",
    repo="razorpay/razorpay-edd",
    ref="master",
    plugin_slug="razorpay-edd",
    endpoint_action="rzp_edd_webhook",
    # EDD's switch has exactly one case: self::ORDER_PAID. Everything else hits `default: return;`.
    events=["order.paid"],
    order_notes_path=("payload", "order", "entity", "notes", "edd_order_id"),
    state_sql="SELECT post_status FROM wp_posts WHERE ID=%(order)d;",
    seed_php="/rig/new_edd_payment.php",
    notes="Fully synchronous, no queue, no cron. One dispatched event.",
    defers_processing=False,
    verifies_amount_at="includes/razorpay-webhook.php:130",   # if($payment['amount'] === $amount)
)

ALL = {t.key: t for t in (WOOCOMMERCE, EDD)}


def expectations(target):
    """What the harness SHOULD find, derived from reading the target -- recorded BEFORE running it.

    Stating the prediction first is the only thing that makes a matching result meaningful. If the
    run disagrees with the prediction, that is the interesting outcome and it must not be quietly
    rewritten afterwards.
    """
    exp = {}
    # P1 needs two independently-scheduled events to race. A target that dispatches one event, or
    # that processes everything synchronously, cannot exhibit the divergence by construction.
    exp["P1-ORDER-INDEPENDENCE"] = (
        "RED" if (target.defers_processing and len(target.events) > 1) else "GREEN")
    exp["P5-AMOUNT-INTEGRITY"] = "GREEN" if target.verifies_amount_at else "RED"
    exp["P4-NO-SILENT-LOSS"] = "RED" if target.defers_processing else "GREEN"
    exp["P3-EVENT-ID-DEDUP"] = "YELLOW"   # structural, advisory for every target so far
    return exp


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 92)
    print("TARGETS -- and what we predict BEFORE running anything")
    print("=" * 92)
    for t in ALL.values():
        print("\n%-14s %s @ %s" % (t.key, t.repo, t.ref))
        print("  endpoint : %s" % t.endpoint_action)
        print("  events   : %s" % ", ".join(t.events))
        print("  notes key: payload.%s" % ".".join(t.order_notes_path[1:]))
        print("  %s" % t.notes)
        print("  amount check: %s" % (t.verifies_amount_at or "ABSENT on the main payment path"))
        print("  PREDICTED  : %s" % ", ".join("%s=%s" % kv for kv in sorted(expectations(t).items())))
