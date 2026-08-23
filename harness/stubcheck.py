#!/usr/bin/env python
"""
Validating the one instrument that had no test: the stub.

Every behavioural verdict in this project is mediated by rig/stub/router.php standing in for
api.razorpay.com. LIMITATIONS.md has always said "the stub is not Razorpay" -- but a disclaimer is
not a measurement, and until now the stub was the only component in the harness with nothing checking
it. If the stub's responses differ from the real API in a way the integration depends on, every
GREEN and every RED downstream is suspect.

This compares the stub's payment response against Razorpay's own documented Payments Entity, and then
does the part that actually matters:

    A missing field is only dangerous if the code under test READS it.

So it greps the integration for accesses to each field and splits the difference into three buckets:

    CRITICAL   documented, read by the integration, absent from the stub
    HARMLESS   documented, absent from the stub, never read by the integration
    EXTRA      returned by the stub but not documented -- the stub inventing reality

CRITICAL is the only bucket that can invalidate a verdict, and it should be empty. If it is not, the
finding is about our harness, not about Razorpay, and it belongs in INCIDENTS.md.

    python harness/stubcheck.py
"""
import io
import json
import os
import re
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RIG = os.path.join(ROOT, "rig")

sys.path.insert(0, HERE)
import dockerenv  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ENTITY_DOC = "https://razorpay.com/docs/build/llm-docs/api/payments/entity.md"
PLUGINS = [
    ("razorpay-woocommerce", os.path.join(RIG, "plugin", "razorpay-woocommerce")),
    ("razorpay-edd", os.path.join(RIG, "plugin", "razorpay-edd")),
]


def documented_fields():
    """The field list Razorpay publish for the Payments Entity, cached into the corpus."""
    cached = os.path.join(ROOT, "spec", "corpus", "api_payments_entity.md")
    if os.path.exists(cached):
        body = io.open(cached, encoding="utf-8").read()
    else:
        req = urllib.request.Request(ENTITY_DOC, headers={"User-Agent": "divergence-stubcheck"})
        body = urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")
        os.makedirs(os.path.dirname(cached), exist_ok=True)
        io.open(cached, "w", encoding="utf-8", newline="\n").write(body)
    return sorted(set(re.findall(r"(?m)^`([a-z_]+)`", body)))


def stub_response():
    """Ask the stub for a payment, exactly as the integration would, from inside the network."""
    p = subprocess.run(
        ["docker", "compose", "exec", "-T", "wordpress", "sh", "-c",
         "curl -s http://rzpstub:8000/v1/payments/pay_RIG00000000001"],
        cwd=RIG, env=dockerenv.shell(), capture_output=True, text=True, timeout=120)
    try:
        return json.loads((p.stdout or "").strip())
    except Exception:
        raise SystemExit("could not read the stub. Is the rig up?  cd rig && ./setup.sh\n"
                         "  got: %r" % (p.stdout or p.stderr or "")[:200])


def fields_read_by(plugin_dir, fields):
    """Which documented fields does this integration actually access?

    PHP reads these as $payment['field'] or ['entity']['field'], so a literal quoted-key search is
    both sufficient and precise enough. Deliberately conservative: if in doubt, count it as read,
    because a false CRITICAL costs us an investigation and a false HARMLESS costs us a wrong verdict.
    """
    if not os.path.isdir(plugin_dir):
        return set()
    blob = []
    for root, _, files in os.walk(plugin_dir):
        if os.sep + ".git" in root:
            continue
        for fn in files:
            if fn.endswith(".php"):
                try:
                    blob.append(io.open(os.path.join(root, fn), encoding="utf-8",
                                        errors="replace").read())
                except OSError:
                    pass
    src = "\n".join(blob)
    return {f for f in fields if re.search(r"""\[\s*['"]%s['"]\s*\]""" % re.escape(f), src)}


def main():
    doc = documented_fields()
    stub = stub_response()
    have = set(stub)

    print("=" * 96)
    print("STUB FIDELITY -- is the thing standing in for Razorpay close enough to trust?")
    print("=" * 96)
    print("documented Payments Entity fields : %d   (%s)" % (len(doc), ENTITY_DOC))
    print("fields the stub returns           : %d\n" % len(have))

    missing = [f for f in doc if f not in have]
    extra = sorted(f for f in have if f not in doc)

    read_by = {}
    for name, path in PLUGINS:
        read_by[name] = fields_read_by(path, doc)
        print("  %-24s reads %d of the %d documented fields" % (name, len(read_by[name]), len(doc)))

    any_read = set().union(*read_by.values()) if read_by else set()
    critical = [f for f in missing if f in any_read]
    harmless = [f for f in missing if f not in any_read]

    print("\n" + "-" * 96)
    print("CRITICAL  documented, READ by an integration, and absent from the stub")
    if critical:
        for f in critical:
            who = ", ".join(n for n, s in read_by.items() if f in s)
            print("    %-22s read by %s" % (f, who))
    else:
        print("    (none)")

    print("\nHARMLESS  documented, absent from the stub, never read by either integration")
    print("    %s" % (", ".join(harmless) if harmless else "(none)"))

    print("\nEXTRA     returned by the stub but not documented -- the stub inventing reality")
    print("    %s" % (", ".join(extra) if extra else "(none)"))

    print("\n" + "=" * 96)
    if critical:
        print("VERDICT: the stub is MISSING FIELDS THE INTEGRATION READS.")
        print("  Any behavioural verdict that depends on those fields is unreliable. This is a")
        print("  finding about our harness, not about Razorpay. Record it in INCIDENTS.md and fix")
        print("  the stub before publishing anything that rests on it.")
    else:
        print("VERDICT: every documented field the integrations actually read is present in the stub.")
        print("  That does not make the stub Razorpay -- it does not reproduce timing, rate limits,")
        print("  partial captures or error taxonomies -- but it does mean no verdict in this")
        print("  repository turns on a field the stub silently omits.")
    print("=" * 96)

    out = os.path.join(RIG, "out", "stub_fidelity.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    io.open(out, "w", encoding="utf-8").write(json.dumps(
        {"documented": doc, "stub_returns": sorted(have),
         "read_by": {k: sorted(v) for k, v in read_by.items()},
         "critical": critical, "harmless": harmless, "extra": extra}, indent=2))
    print("saved -> %s" % os.path.relpath(out, ROOT))
    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main())
