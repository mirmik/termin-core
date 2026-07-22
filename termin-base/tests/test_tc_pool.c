#include <tcbase/tc_log.h>
#include <tcbase/tc_pool.h>

#include "guard_c.h"
#include <string.h>

static int captured_count = 0;
static tc_log_level captured_level = TC_LOG_DEBUG;
static char captured_message[256];

static void capture_log(tc_log_level level, const char* message) {
    captured_count++;
    captured_level = level;
    strncpy(captured_message, message ? message : "", sizeof(captured_message) - 1);
    captured_message[sizeof(captured_message) - 1] = '\0';
}

int main(void) {
    tc_pool pool;
    GUARD_C_CHECK(tc_pool_init(&pool, sizeof(int), 1));

    tc_handle handle = tc_pool_alloc(&pool);
    GUARD_C_CHECK(!tc_handle_is_invalid(handle));
    GUARD_C_CHECK(tc_pool_get_checked(&pool, handle, "test_resource") != NULL);

    tc_log_set_callback(capture_log);
    tc_log_set_level(TC_LOG_DEBUG);

    GUARD_C_CHECK(tc_pool_is_valid(&pool, handle));
    GUARD_C_CHECK(captured_count == 0);

    GUARD_C_CHECK(tc_pool_free_slot(&pool, handle));
    GUARD_C_CHECK(!tc_pool_is_valid(&pool, handle));
    GUARD_C_CHECK(captured_count == 0);

    GUARD_C_CHECK(tc_pool_get_checked(&pool, handle, "test_resource") == NULL);
    GUARD_C_CHECK(captured_count == 1);
    GUARD_C_CHECK(captured_level == TC_LOG_ERROR);
    GUARD_C_CHECK(strstr(captured_message, "type=test_resource") != NULL);
    GUARD_C_CHECK(strstr(captured_message, "index=0") != NULL);
    GUARD_C_CHECK(strstr(captured_message, "generation=1") != NULL);

    tc_log_set_callback(NULL);
    tc_pool_free(&pool);
    return 0;
}
