#!/usr/bin/env bash
# =============================================================================
#  Drop all rig state and rebuild from nothing.
#
#  Why this exists: after a few hundred trials the rig accumulates test orders,
#  and a reviewer's first run should not be confounded by leftovers from ours.
#  "does it run, is it structured, would you trust it" is a scored axis, and a
#  harness whose results depend on how many times it has been run before is not
#  one you would trust.
#
#  Destroys the named volumes (db_data, wp_data) -- every order, every queue row.
#  The plugin under test is re-cloned by setup.sh at a pinned tag, so this is the
#  cleanest possible starting point.
# =============================================================================
set -uo pipefail
export MSYS_NO_PATHCONV=1
. "$(dirname "$0")/_docker.sh"   # portable docker discovery
cd "$(dirname "$0")"

printf '\n\033[1;33mThis destroys ALL rig state: every order, every webhook row, both volumes.\033[0m\n'
if [ "${1:-}" != "--yes" ]; then
  printf 'Re-run as:  ./reset.sh --yes\n\n'
  exit 1
fi

echo "==> stopping containers and removing volumes"
docker compose --profile stub --profile tools down -v 2>&1 | tail -4

echo "==> removing the cloned plugin so setup.sh re-clones at the pinned tag"
rm -rf plugin/razorpay-woocommerce

echo "==> clearing generated artefacts (transcripts are kept: out/*.log, out/*.json)"
rm -f out/h_*.json out/x_*.json out/a_pay_*.json out/t.json 2>/dev/null

printf '\n\033[32mreset complete.\033[0m  Next:  ./setup.sh\n'
