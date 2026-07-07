#include <stdio.h>
#include <string.h>

#include "guard_c.h"

#include <tcbase/tc_string.h>

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
    GUARD_C_RUN(test_tc_intern_string_survives_table_growth);
    GUARD_C_RUN(test_tc_intern_string_null_is_null);
    tc_intern_cleanup();
    return GUARD_C_END();
}
