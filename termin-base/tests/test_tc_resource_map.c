#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "guard_c.h"

#include <tcbase/tc_resource_map.h>

static int g_destroy_count = 0;

static void destroy_int(void* value) {
    free(value);
    ++g_destroy_count;
}

static int* make_int(int value) {
    int* result = (int*)malloc(sizeof(int));
    if (result) {
        *result = value;
    }
    return result;
}

static char* duplicate_key(const char* key) {
    size_t size = strlen(key) + 1;
    char* result = (char*)malloc(size);
    if (result) {
        memcpy(result, key, size);
    }
    return result;
}

GUARD_C_TEST(test_resource_map_reserve_and_owned_key_insert) {
    g_destroy_count = 0;
    tc_resource_map* map = tc_resource_map_new(destroy_int);
    GUARD_C_REQUIRE(map != NULL);
    GUARD_C_REQUIRE(tc_resource_map_reserve(map, 32));

    char* key = duplicate_key("prepared");
    int* value = make_int(17);
    GUARD_C_REQUIRE(key != NULL);
    GUARD_C_REQUIRE(value != NULL);
    GUARD_C_CHECK(tc_resource_map_add_owned_key(map, key, value));
    GUARD_C_CHECK(*(int*)tc_resource_map_get(map, "prepared") == 17);

    char* duplicate = duplicate_key("prepared");
    int* rejected = make_int(29);
    GUARD_C_REQUIRE(duplicate != NULL);
    GUARD_C_REQUIRE(rejected != NULL);
    GUARD_C_CHECK(!tc_resource_map_add_owned_key(map, duplicate, rejected));
    free(duplicate);
    free(rejected);
    GUARD_C_CHECK(tc_resource_map_count(map) == 1);

    tc_resource_map_free(map);
    GUARD_C_CHECK(g_destroy_count == 1);
    return 0;
}

GUARD_C_TEST(test_resource_map_failed_reserve_preserves_contents) {
    tc_resource_map* map = tc_resource_map_new(destroy_int);
    GUARD_C_REQUIRE(map != NULL);
    int* value = make_int(41);
    GUARD_C_REQUIRE(value != NULL);
    GUARD_C_REQUIRE(tc_resource_map_add(map, "stable", value));

    GUARD_C_CHECK(!tc_resource_map_reserve(map, SIZE_MAX));
    GUARD_C_CHECK(tc_resource_map_count(map) == 1);
    GUARD_C_CHECK(*(int*)tc_resource_map_get(map, "stable") == 41);

    tc_resource_map_free(map);
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_resource_map_reserve_and_owned_key_insert);
    GUARD_C_RUN(test_resource_map_failed_reserve_preserves_contents);
    return GUARD_C_END();
}
