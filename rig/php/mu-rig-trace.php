<?php
/*
 * Plugin Name: RIG - query trace
 * Description: TEST RIG ONLY. Records every database query the integration issues during a webhook
 *              delivery, so the harness can show what the plugin actually did rather than assert it.
 *              Does not modify the plugin under test.
 *
 * WordPress routes every database accessor through one place -- wpdb::query(), which calls
 * apply_filters('query', $query) at wp-includes/class-wpdb.php:2234. insert/update/delete/replace
 * and get_results/get_row/get_var/get_col all funnel through it. So a filter here sees everything
 * the plugin does to the database, with the plugin's bytes unchanged.
 *
 * Why this earns its place: the harness's verdicts are about merchant-visible STATE. A reviewer's
 * next question is "how do you know it dropped the refund rather than recording it somewhere I am
 * not looking?" The honest answer is a trace: here is every statement that delivery issued, and
 * none of them touched the refund tables. An absence is much more convincing when it is an absence
 * in a complete record.
 *
 * Written to a table rather than a file because the harness already speaks SQL to this database,
 * and because a file would need another mount and another failure mode.
 */

add_action('plugins_loaded', function () {
    global $wpdb;
    $t = $wpdb->prefix . 'rig_query_trace';
    if (get_option('rig_trace_installed') !== $t) {
        $wpdb->query("CREATE TABLE IF NOT EXISTS `$t` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `at` DOUBLE NOT NULL,
            `req` VARCHAR(64) NOT NULL,
            `verb` VARCHAR(16) NOT NULL,
            `tbl` VARCHAR(128) NOT NULL,
            `sql_text` TEXT NOT NULL,
            PRIMARY KEY (`id`), KEY `req` (`req`)
        ) DEFAULT CHARSET=utf8mb4");
        update_option('rig_trace_installed', $t);
    }
}, 1);

/**
 * One identifier per HTTP delivery, so a trace can be attributed to the webhook that caused it.
 * Razorpay send x-razorpay-event-id on every delivery; the harness sends it too. If it is absent
 * we fall back to a per-request random, which still groups correctly -- it just cannot be joined
 * back to a specific event.
 */
function rig_trace_request_id() {
    static $id = null;
    if ($id === null) {
        if (!empty($_SERVER['HTTP_X_RAZORPAY_EVENT_ID'])) {
            $id = substr(preg_replace('/[^A-Za-z0-9_-]/', '', $_SERVER['HTTP_X_RAZORPAY_EVENT_ID']), 0, 64);
        } else {
            $id = 'req_' . substr(md5(uniqid('', true)), 0, 16);
        }
    }
    return $id;
}

add_filter('query', function ($query) {
    // Only trace webhook deliveries. Tracing every admin page load would bury the signal, and the
    // harness only ever asks about deliveries.
    $action = isset($_REQUEST['action']) ? $_REQUEST['action'] : '';
    if (strpos($action, 'rzp_') !== 0) {
        return $query;
    }

    global $wpdb;
    $t = $wpdb->prefix . 'rig_query_trace';

    // Never trace our own writes, or this recurses forever.
    if (strpos($query, 'rig_query_trace') !== false) {
        return $query;
    }

    $verb = strtoupper(strtok(ltrim($query), " \n\t"));
    $tbl = '';
    if (preg_match('/\b(?:FROM|INTO|UPDATE|TABLE)\s+`?([A-Za-z0-9_]+)`?/i', $query, $m)) {
        $tbl = $m[1];
    }

    $wpdb->query($wpdb->prepare(
        "INSERT INTO `$t` (`at`,`req`,`verb`,`tbl`,`sql_text`) VALUES (%f,%s,%s,%s,%s)",
        microtime(true), rig_trace_request_id(), $verb, $tbl, substr($query, 0, 2000)
    ));

    return $query;
}, 1);
