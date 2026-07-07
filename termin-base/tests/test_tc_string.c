#include <stdio.h>
#include <string.h>

#include "guard_c.h"

#include <tcbase/tc_string.h>

typedef struct InternVisitState {
    size_t count;
    int saw_alpha;
    int saw_beta;
    size_t max_depth_seen;
} InternVisitState;

static void visit_intern_string(
    const char* string,
    size_t bucket_index,
    size_t depth_in_bucket,
    void* user_data
) {
    (void)bucket_index;
    InternVisitState* state = (InternVisitState*)user_data;
    ++state->count;
    if (strcmp(string, "alpha") == 0) {
        state->saw_alpha = 1;
    }
    if (strcmp(string, "beta") == 0) {
        state->saw_beta = 1;
    }
    if (depth_in_bucket > state->max_depth_seen) {
        state->max_depth_seen = depth_in_bucket;
    }
}

GUARD_C_TEST(test_tc_intern_string_canonicalizes_equal_strings) {
    const char* first = tc_intern_string("alpha");
    const char* second = tc_intern_string("alpha");
    const char* third = tc_intern_string("beta");

    GUARD_C_REQUIRE(first != NULL);
    GUARD_C_REQUIRE(second != NULL);
    GUARD_C_REQUIRE(third != NULL);
    GUARD_C_CHECK(first == second);
    GUARD_C_CHECK(first != third);
    GUARD_C_CHECK_STREQ("alpha", first);
    GUARD_C_CHECK_STREQ("beta", third);

    return 0;
}

GUARD_C_TEST(test_tc_intern_string_reports_table_state) {
    tc_intern_string_stats stats = tc_intern_string_get_stats();
    GUARD_C_CHECK(stats.entry_count >= 2);
    GUARD_C_CHECK(stats.bucket_count >= 256);
    GUARD_C_CHECK(stats.non_empty_bucket_count > 0);
    GUARD_C_CHECK(stats.max_bucket_depth > 0);

    InternVisitState state = {0};
    tc_intern_string_foreach(visit_intern_string, &state);
    GUARD_C_CHECK(state.count == stats.entry_count);
    GUARD_C_CHECK(state.saw_alpha);
    GUARD_C_CHECK(state.saw_beta);
    GUARD_C_CHECK(state.max_depth_seen < stats.max_bucket_depth);

    return 0;
}

GUARD_C_TEST(test_tc_intern_string_survives_table_growth) {
    const char* sentinel = tc_intern_string("stable-sentinel");
    GUARD_C_REQUIRE(sentinel != NULL);

    for (int i = 0; i < 700; ++i) {
        char buffer[64];
        snprintf(buffer, sizeof(buffer), "generated-intern-string-%04d", i);
        const char* interned = tc_intern_string(buffer);
        GUARD_C_REQUIRE(interned != NULL);
        GUARD_C_CHECK_STREQ(buffer, interned);
    }

    const char* sentinel_again = tc_intern_string("stable-sentinel");
    GUARD_C_REQUIRE(sentinel_again != NULL);
    GUARD_C_CHECK(sentinel == sentinel_again);
    GUARD_C_CHECK_STREQ("stable-sentinel", sentinel_again);

    return 0;
}

GUARD_C_TEST(test_tc_intern_string_null_is_null) {
    GUARD_C_CHECK(tc_intern_string(NULL) == NULL);
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_tc_intern_string_canonicalizes_equal_strings);
    GUARD_C_RUN(test_tc_intern_string_reports_table_state);
    GUARD_C_RUN(test_tc_intern_string_survives_table_growth);
    GUARD_C_RUN(test_tc_intern_string_null_is_null);
    tc_intern_cleanup();
    return GUARD_C_END();
}
