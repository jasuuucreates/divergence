"""Security/privacy sweep. Reports FILE PATHS ONLY -- never prints a secret value."""
import os, re, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SKIP = {".git", "node_modules", "__pycache__", ".pytest_cache", ".idea", ".vscode"}
DOTENV = "." + "env"

PATS = {
    "razorpay LIVE key":  re.compile(r"rzp_" + r"live_[A-Za-z0-9]{6,}"),
    "razorpay TEST key":  re.compile(r"rzp_" + r"test_[A-Za-z0-9]{6,}"),
    "anthropic key":      re.compile(r"sk-" + r"ant-[A-Za-z0-9_\-]{20,}"),
    "stripe live key":    re.compile(r"sk_" + r"live_[A-Za-z0-9]{10,}"),
    "github token":       re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "aws access key":     re.compile(r"AKIA[0-9A-Z]{16}"),
    "bearer token":       re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{25,}"),
    "operator email":     re.compile(r"jusnoor\w*@\w+"),
    "card-like 16 digit": re.compile(r"\b(?:\d[ -]?){15}\d\b"),
    "PAN-like":           re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "private key block":  re.compile(r"BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY"),
    "webhook secret lit": re.compile(r"webhook[_-]?secret\s*[=:]\s*['\"][^'\"]{8,}"),
}
BIN = (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".mp4", ".zip", ".lz4",
       ".woff", ".woff2", ".ico", ".pyc", ".gz", ".tar")

root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
hits = {k: [] for k in PATS}
sensitive_files = []
n = 0
for root, dirs, files in os.walk(root_dir):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        p = os.path.join(root, f)
        low = f.lower()
        if low.startswith(DOTENV) or low.endswith((".pem", ".key", ".p12", ".pfx")) or "cookie" in low:
            sensitive_files.append(p)
        if low.endswith(BIN):
            continue
        try:
            if os.path.getsize(p) > 4_000_000:
                continue
            t = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        n += 1
        for k, rx in PATS.items():
            if rx.search(t):
                hits[k].append(p)

print("scanned %d text files under %s\n" % (n, os.path.abspath(root_dir)))
clean = True
for k, v in hits.items():
    if v:
        clean = False
        print("  [%3d] %s" % (len(v), k))
        for p in v[:8]:
            print("        %s" % p)
print("\nSENSITIVE FILES PRESENT (%d):" % len(sensitive_files))
for p in sensitive_files:
    print("   ", p)
if clean and not sensitive_files:
    print("\n>>> CLEAN: no secret patterns and no sensitive files found.")
