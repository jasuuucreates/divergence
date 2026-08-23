"""
The specification oracle.

Every property here is derived from a sentence Razorpay themselves published. That is the whole
point: this harness does not test our opinion of how a payment integration should behave, it tests
the integration against its own vendor's documented contract. Each property therefore carries the
verbatim source sentence and the URL it came from, and the report prints them, so a reviewer can
check the premise as easily as the verdict.

Sources fetched 2026-08-23:
  https://razorpay.com/docs/build/llm-docs/webhooks/validate-test.md
  (Razorpay publish every docs page as markdown under /docs/build/llm-docs/, indexed from llms.txt.)
"""

DOCS_URL = "https://razorpay.com/docs/build/llm-docs/webhooks/validate-test.md"


class Property:
    """One checkable claim, with the vendor sentence that makes it normative."""

    def __init__(self, key, title, doc_quote, doc_url, rationale, verdict_kind):
        self.key = key
        self.title = title
        self.doc_quote = doc_quote
        self.doc_url = doc_url
        self.rationale = rationale
        # "behavioural" -> only decidable by executing the integration
        # "structural"  -> decidable by reading source, and therefore WEAKER evidence
        self.verdict_kind = verdict_kind

    def __repr__(self):
        return "<Property %s (%s)>" % (self.key, self.verdict_kind)


ORDER_INDEPENDENCE = Property(
    key="P1-ORDER-INDEPENDENCE",
    title="All legal delivery orderings of the same events must converge to the same terminal state",
    doc_quote=(
        "Ideally, you should receive a webhook in the order in which the webhook events occur. "
        "However, you may not always receive the webhooks in the order."
    ),
    doc_url=DOCS_URL,
    rationale=(
        "Razorpay states delivery order is not guaranteed. An integration that reaches a different "
        "merchant-visible terminal state depending on arrival order is therefore not merely unlucky, "
        "it is non-conforming: the vendor has told it that this input is legal. We assert CONFLUENCE "
        "over the converged state -- read only after every deferred queue has drained -- so "
        "'a transient our cron fixes' is not an available rebuttal."
    ),
    verdict_kind="behavioural",
)

DUPLICATE_TOLERANCE = Property(
    key="P2-DUPLICATE-TOLERANCE",
    title="Redelivering an event must not change the terminal state",
    doc_quote=(
        "There could be scenarios where your endpoint might receive the same webhook event multiple "
        "times. This is an expected behaviour based on the webhook design."
    ),
    doc_url=DOCS_URL,
    rationale=(
        "At-least-once delivery is stated by the vendor as expected behaviour, not as an edge case. "
        "Delivering the same event twice must therefore be idempotent with respect to the "
        "merchant-visible state. This is the property that catches double-fulfilment and "
        "double-refund."
    ),
    verdict_kind="behavioural",
)

EVENT_ID_DEDUP = Property(
    key="P3-EVENT-ID-DEDUP",
    title="The integration uses x-razorpay-event-id to identify duplicate deliveries",
    # Shortened 2026-08-23: the previous version concatenated three numbered list items into one
    # "quotation". Nothing was invented, but it was reconstructed rather than quoted, and
    # harness/gate.py's G1 check correctly refused it. Now a single contiguous sentence.
    doc_quote=(
        "You can identify the duplicate webhooks using the x-razorpay-event-id header. "
        "The value for this header is unique per event."
    ),
    doc_url=DOCS_URL,
    rationale=(
        "This is the remedy the vendor itself prescribes for the hazard it itself documents. "
        "NOTE THE WEAKNESS: this one is STRUCTURAL. Absence of the header proves the prescribed "
        "mechanism is absent; it does NOT prove the integration is non-idempotent, because an "
        "integration may de-duplicate some other way. It is reported as an advisory, never as a "
        "failure, and P2 is what actually decides idempotence."
    ),
    verdict_kind="structural",
)

NO_SILENT_LOSS = Property(
    key="P4-NO-SILENT-LOSS",
    title="An accepted event must either change the state or be explicitly recorded as ignored",
    # UPGRADED 2026-08-23 by harness/specmine.py. The original citation here was the at-least-once
    # sentence, and the "2xx means you took responsibility" step was OUR INFERENCE. Mining the
    # documentation corpus turned up Razorpay stating both halves outright, so the property no longer
    # rests on an inference at all. Both sentences verified byte-for-byte in spec/corpus/.
    doc_quote=(
        "Please make sure the API responds with 2xx when you successfully consume the event at your "
        "end. ... In this approach, if we do not receive a successful response from your server, we "
        "resend the webhook."
    ),
    doc_url="https://razorpay.com/docs/build/llm-docs/webhooks/best-practices.md",
    rationale=(
        "Razorpay define 2xx as meaning the event was SUCCESSFULLY CONSUMED, and state that they "
        "resend only when they do not get a successful response. Those two sentences together make "
        "this a direct contract obligation rather than a corollary: an endpoint that answers 2xx and "
        "then neither changes state nor durably records the event has told the sender the money "
        "event was consumed, and has thereby guaranteed it will never be resent. "
        "This is the property that catches 'marked processed, did nothing'."
    ),
    verdict_kind="behavioural",
)

AMOUNT_INTEGRITY = Property(
    key="P5-AMOUNT-INTEGRITY",
    title="An order must not reach a paid state for an amount other than the amount ordered",
    # VERBATIM, fetched 2026-08-23. Note honestly what this quote does and does not establish:
    # it fixes the UNITS and says the order was created FOR that amount. The normative force of the
    # invariant itself comes from Razorpay's own code, which implements it twice (see rationale).
    # An earlier draft of this file paraphrased a quote here. That is the exact fabrication pattern
    # this project criticises elsewhere, so it was replaced with a fetched sentence.
    # Shortened 2026-08-23 for the same reason: the previous version prepended a table cell
    # ("amount : integer") and included a currency symbol that Razorpay's own markdown export
    # strips, so it did not exist verbatim anywhere. G1 refused it. This sentence does exist.
    doc_quote="The amount for which the order was created, in currency subunits.",
    doc_url="https://razorpay.com/docs/build/llm-docs/api/orders/create.md",
    rationale=(
        "This property is not our invention -- it is the vendor's own, and they evidence it twice in "
        "their own code. razorpay-woocommerce enforces it at razorpay-webhook.php:505 on the "
        "virtual-account path ($amountPaid === $amount), and razorpay-edd enforces it at line 130 "
        "($payment['amount'] === $amount). It is absent from paymentAuthorized(), the path that "
        "handles ordinary card and UPI payments, where the expected amount is computed and then used "
        "only as a capture argument. A property the vendor implements in two sibling paths and omits "
        "in the main one is exactly what a conformance oracle exists to surface. "
        "SCOPE: this is a MISSING INVARIANT, not a demonstrated attack -- the signature is verified "
        "and the payment entity is fetched from Razorpay, so an attacker does not simply choose the "
        "amount. What is shown is that the integration does not defend the invariant itself."
    ),
    verdict_kind="behavioural",
)

ALL_PROPERTIES = [ORDER_INDEPENDENCE, DUPLICATE_TOLERANCE, EVENT_ID_DEDUP, NO_SILENT_LOSS,
                  AMOUNT_INTEGRITY]


def citations():
    """Everything a reviewer needs to audit the premises, without running anything."""
    out = []
    for p in ALL_PROPERTIES:
        out.append({
            "key": p.key,
            "title": p.title,
            "kind": p.verdict_kind,
            "vendor_says": p.doc_quote,
            "source": p.doc_url,
            "why_it_follows": p.rationale,
        })
    return out


if __name__ == "__main__":
    import json
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 100)
    print("THE CONTRACT -- every property below is derived from a sentence Razorpay published")
    print("=" * 100)
    for c in citations():
        print("\n%-24s [%s]" % (c["key"], c["kind"].upper()))
        print("  claim   : %s" % c["title"])
        print("  vendor  : \"%s\"" % c["vendor_says"])
        print("  source  : %s" % c["source"])
    print("\n%d properties, %d behavioural (decided by execution), %d structural (advisory only)"
          % (len(ALL_PROPERTIES),
             sum(1 for p in ALL_PROPERTIES if p.verdict_kind == "behavioural"),
             sum(1 for p in ALL_PROPERTIES if p.verdict_kind == "structural")))
