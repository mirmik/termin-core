#include <tcbase/tc_log.h>

#include "guard_c.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

static int g_callback_count = 0;
static tc_log_level g_callback_level = TC_LOG_DEBUG;
static char g_callback_message[TC_LOG_MESSAGE_CAPACITY];

static void capture_callback(tc_log_level level, const char* message) {
    g_callback_count += 1;
    g_callback_level = level;
    snprintf(g_callback_message, sizeof(g_callback_message), "%s", message ? message : "");
}

static void reset_logging(void) {
    tc_log_capture_stop();
    tc_log_set_callback(NULL);
    tc_log_set_level(TC_LOG_DEBUG);
    g_callback_count = 0;
    g_callback_level = TC_LOG_DEBUG;
    g_callback_message[0] = '\0';
}

static void test_capture_preserves_callback_and_drops_oldest(void) {
    reset_logging();
    tc_log_set_callback(capture_callback);
    GUARD_C_CHECK(tc_log_capture_start(2));

    tc_log_info("first");
    tc_log_warn("second");
    tc_log_error("third");

    GUARD_C_CHECK(g_callback_count == 3);
    GUARD_C_CHECK(g_callback_level == TC_LOG_ERROR);
    GUARD_C_CHECK(strcmp(g_callback_message, "third") == 0);

    tc_log_record records[2];
    uint64_t dropped = 0;
    size_t count = tc_log_capture_drain(records, 2, &dropped);
    GUARD_C_CHECK(count == 2);
    GUARD_C_CHECK(dropped == 1);
    GUARD_C_CHECK(records[0].level == TC_LOG_WARN);
    GUARD_C_CHECK(strcmp(records[0].message, "second") == 0);
    GUARD_C_CHECK(records[1].level == TC_LOG_ERROR);
    GUARD_C_CHECK(strcmp(records[1].message, "third") == 0);

    dropped = 9;
    count = tc_log_capture_drain(records, 2, &dropped);
    GUARD_C_CHECK(count == 0);
    GUARD_C_CHECK(dropped == 0);
    reset_logging();
}

static void test_stop_disables_capture_only(void) {
    reset_logging();
    tc_log_set_callback(capture_callback);
    GUARD_C_CHECK(tc_log_capture_start(1));
    tc_log_capture_stop();

    tc_log_info("after stop");

    tc_log_record record;
    uint64_t dropped = 0;
    GUARD_C_CHECK(tc_log_capture_drain(&record, 1, &dropped) == 0);
    GUARD_C_CHECK(dropped == 0);
    GUARD_C_CHECK(g_callback_count == 1);
    GUARD_C_CHECK(strcmp(g_callback_message, "after stop") == 0);
    reset_logging();
}

int main(void) {
    test_capture_preserves_callback_and_drops_oldest();
    test_stop_disables_capture_only();
    return 0;
}
