#!/usr/bin/env bash
# =============================================================================
#  Panic button for a live demonstration.
#
#      ./snapshot.sh save       capture the current database as known-good
#      ./snapshot.sh restore    put it back
#      ./snapshot.sh status     what is stored, and how stale
#
#  Why this exists: ./reset.sh && ./setup.sh takes about three minutes. That is
#  fine at a desk and fatal in front of an audience. A database snapshot restores
#  in roughly two seconds, which turns "give me five minutes" into "give me a
#  moment" -- and being able to say that calmly is most of the value.
#
#  Take a snapshot immediately after setup, while the rig is known good. Then any
#  demo that goes sideways -- a half-processed order, a plugin left deactivated by
#  a previous run, orders accumulated from testing -- is one command from clean.
#
#  This snapshots the DATABASE only. The plugin under test, the containers and the
#  stub are unaffected, which is correct: those are pinned and verified separately
#  by demo.py --preflight. If the plugin itself is dirty, restore will not fix it,
#  and preflight will tell you so.
# =============================================================================
set -uo pipefail
. "$(dirname "$0")/_docker.sh"
cd "$(dirname "$0")"

SNAP_DIR="out"
SNAP="$SNAP_DIR/snapshot.sql"
DC="docker compose"

ok()  { printf '    \033[32m%s\033[0m\n' "$*"; }
warn(){ printf '    \033[1;33m%s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mFAIL: %s\033[0m\n' "$*" >&2; exit 1; }

case "${1:-}" in

  save)
    mkdir -p "$SNAP_DIR"
    $DC exec -T db sh -c \
      'mariadb-dump -uroot -proot --skip-ssl --single-transaction --routines wordpress' \
      > "$SNAP" 2>/dev/null || die "dump failed -- is the db container running?"
    [ -s "$SNAP" ] || die "dump produced an empty file; refusing to call that a snapshot"
    ORDERS=$($DC exec -T db mariadb -uroot -proot --skip-ssl -N -B wordpress \
      -e "SELECT COUNT(*) FROM wp_posts WHERE post_type='shop_order';" 2>/dev/null | tr -d '\r')
    date -u +"%Y-%m-%dT%H:%M:%SZ" > "$SNAP_DIR/snapshot.stamp"
    ok "saved $(wc -c < "$SNAP" | tr -d ' ') bytes  (${ORDERS:-?} orders at snapshot time)"
    ;;

  restore)
    [ -s "$SNAP" ] || die "no snapshot at $SNAP -- run ./snapshot.sh save first"
    # Restore into the live database. mariadb-dump writes DROP/CREATE per table, so this
    # replaces state rather than merging into it.
    $DC exec -T db mariadb -uroot -proot --skip-ssl wordpress < "$SNAP" 2>/dev/null \
      || die "restore failed"
    ORDERS=$($DC exec -T db mariadb -uroot -proot --skip-ssl -N -B wordpress \
      -e "SELECT COUNT(*) FROM wp_posts WHERE post_type='shop_order';" 2>/dev/null | tr -d '\r')
    ok "restored  (${ORDERS:-?} orders)"
    warn "the plugin under test is NOT touched by this. Run: python harness/demo.py --preflight"
    ;;

  status)
    if [ -s "$SNAP" ]; then
      ok "snapshot: $(wc -c < "$SNAP" | tr -d ' ') bytes, taken $(cat "$SNAP_DIR/snapshot.stamp" 2>/dev/null || echo '?')"
    else
      warn "no snapshot stored"
    fi
    ;;

  *)
    echo "usage: ./snapshot.sh {save|restore|status}"
    echo
    echo "  Take a snapshot right after setup, while the rig is known good."
    echo "  Restore takes ~2s. ./reset.sh && ./setup.sh takes ~3 minutes."
    exit 1
    ;;
esac
