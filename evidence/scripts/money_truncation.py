#!/usr/bin/env python
"""
The honest version of the money-truncation number.

An adversarial review destroyed our original headline and it deserved to:

    "6.62% of prices lose a paisa"  was measured over UNIFORM-RANDOM paise.
    Real catalogues do not price uniformly. They price at .99, .95, .00, .50.

Uniform sampling is not a property of merchants, it is a property of our sampler, and a reviewer who
asks "what price distribution?" ends the conversation. So this script drops the uniform number
entirely and measures the rate the way a merchant would actually experience it: PER PRICE ENDING.

The result is both more defensible AND worse for the affected endings, which is the usual outcome of
replacing a manufactured statistic with a measured one.

The defect under test is the code Razorpay's own MCP generator emits for 6 of its languages:
    int(amount * 100)   /   (int)(amount * 100)   /   (amount * 100).to_i   /   as i64
versus the correct form its JavaScript templates use:
    Math.round(amount * 100)
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Endings ordered roughly by how common they are in real retail catalogues.
ENDINGS = ["00", "99", "50", "95", "90", "49", "25", "75", "98", "45", "19", "29", "89", "79"]
MAX_RUPEES = 100000  # Rs 1 .. Rs 1,00,000 -- covers essentially any Indian e-commerce price


def truncates(rupee_string):
    """Does the generated code undercharge for this exact price?

    The generated code receives a JSON number and does int(amount*100).
    The correct answer is the exact paise value the merchant typed.
    """
    p = float(rupee_string)
    correct = round(p * 100)          # what the merchant means
    emitted = int(p * 100.0)          # what the generated code sends to Razorpay
    return emitted != correct, correct, emitted


def main():
    print("=" * 84)
    print("PAISA LOSS BY PRICE ENDING  --  int(amount*100) vs round(amount*100)")
    print("=" * 84)
    print("%-8s %-10s %-10s %-9s  %s" % ("ENDING", "PRICES", "UNDER", "RATE", "example"))
    print("-" * 84)

    rows = []
    for e in ENDINGS:
        bad = 0
        example = None
        for w in range(1, MAX_RUPEES + 1):
            s = "%d.%s" % (w, e)
            t, correct, emitted = truncates(s)
            if t:
                bad += 1
                if example is None:
                    example = "Rs %s -> %d paise, not %d" % (s, emitted, correct)
        rate = 100.0 * bad / MAX_RUPEES
        rows.append({"ending": "." + e, "tested": MAX_RUPEES, "undercharged": bad,
                     "rate_pct": round(rate, 2), "example": example})
        print("%-8s %-10d %-10d %-8.2f%%  %s" % ("." + e, MAX_RUPEES, bad, rate, example or "-"))

    print("-" * 84)
    safe = [r for r in rows if r["undercharged"] == 0]
    print("endings NEVER affected : %s" % ", ".join(r["ending"] for r in safe))
    print("  (0.5 and 0.25 are exact in binary floating point, so x.00/.25/.50/.75 multiply cleanly)")

    # RANGE SENSITIVITY -- the finding that killed our original headline.
    print()
    print("=" * 84)
    print("WHY WE DO NOT SHIP A SINGLE PERCENTAGE")
    print("=" * 84)
    print("The rate depends on the RANGE as well as the ending, because the spacing of")
    print("representable doubles grows with magnitude. Same ending, different ranges:")
    print()
    print("  %-8s %-14s %-14s %s" % ("ENDING", "Rs 1-5,000", "Rs 1-100,000", "ratio"))
    for e in ("99", "95", "90", "29"):
        r1 = sum(1 for w in range(1, 5001) if truncates("%d.%s" % (w, e))[0]) / 5000.0 * 100
        r2 = [r for r in rows if r["ending"] == "." + e][0]["rate_pct"]
        print("  %-8s %-14s %-14s %s" % ("." + e, "%.2f%%" % r1, "%.2f%%" % r2,
                                         "%.0fx" % (r1 / r2) if r2 else "-"))
    print()
    print("An 11.9% and a 0.59% for the SAME price ending, from the same defect, differing only")
    print("in the range sampled. Our original headline -- 6.62% over uniform-random paise -- was")
    print("therefore a property of the sampler, not of any merchant. It is retracted.")
    print()
    print("WHAT WE CLAIM INSTEAD (deterministic, checkable in one line, no distribution assumed):")
    print("  int(amount*100) undercharges by exactly one paisa on a deterministic, price-dependent")
    print("  subset of inputs. Rs 8.95 -> 894 instead of 895. Rs 16.90 -> 1689 instead of 1690.")
    print("  Rs 8.29 -> 828 instead of 829. Prices ending .00/.25/.50/.75 are never affected.")
    print("  Razorpay's JavaScript templates use Math.round and are correct; six other languages")
    print("  truncate. The defect is certain; the population rate is not ours to assert.")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "money_truncation.json")
    io.open(out, "w", encoding="utf-8").write(json.dumps(
        {"max_rupees": MAX_RUPEES, "method": "exhaustive over integer rupee values per ending",
         "rows": rows}, indent=2))
    print("\nsaved -> experiments/money_truncation.json")


if __name__ == "__main__":
    main()
