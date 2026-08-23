#!/usr/bin/env bash
set -euo pipefail
export MSYS_NO_PATHCONV=1; export MSYS2_ARG_CONV_EXCL='*'
cd "$(dirname "$0")"; . ./rig-state.sh
DC="docker compose"
$DC exec -T db mariadb -uroot -proot --skip-ssl wordpress -e \
 "UPDATE wp_rzp_webhook_requests SET rzp_webhook_notified_at = rzp_webhook_notified_at - 301
   WHERE rzp_update_order_cron_status = 0 AND rzp_webhook_notified_at IS NOT NULL;"
$DC run --rm -T cli wp cron event run rzp_webhook_exec_cron \
  || $DC run --rm -T cli wp eval 'do_action("rzp_webhook_exec_cron");'
$DC run --rm -T cli wp eval "echo 'order_status=' . wc_get_order($ORDER_ID)->get_status() . \"\n\";"
