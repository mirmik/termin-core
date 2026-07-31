#include <tcbase/tc_log.h>
#include <tcbase/tc_pool.h>

#include "guard_c.h"
#include <string.h>

static int captured_count = 0;
static tc_log_level captured_level = TC_LOG_DEBUG;
static char captured_message[256];

typedef struct failing_allocator {
    size_t successful_allocations_before_failure;
} failing_allocator;

static void* failing_allocate(size_t size, void* user_data) {
    failing_allocator* allocator = (failing_allocator*)user_data;
    if (allocator->successful_allocations_before_failure == 0) return NULL;
    allocator->successful_allocations_before_failure--;
    return malloc(size);
}

static void failing_deallocate(void* ptr, void* user_data) {
    (void)user_data;
    free(ptr);
}

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

    for (size_t successful = 0; successful < 4; ++successful) {
        failing_allocator allocator = {successful};
        const tc_pool_config config = {
            .max_capacity = 2,
            .initial_generation = 0,
            .allocate_low_indices_first = true,
            .name = "test_pool",
            .allocate = failing_allocate,
            .deallocate = failing_deallocate,
            .allocator_user_data = &allocator,
        };
        GUARD_C_CHECK(!tc_pool_init_ex(&pool, sizeof(int), 1, &config));
        GUARD_C_CHECK(pool.data == NULL);
        GUARD_C_CHECK(pool.capacity == 0);
    }

    failing_allocator allocator = {8};
    const tc_pool_config config = {
        .max_capacity = 2,
        .initial_generation = 0,
        .allocate_low_indices_first = true,
        .name = "test_pool",
        .allocate = failing_allocate,
        .deallocate = failing_deallocate,
        .allocator_user_data = &allocator,
    };
    GUARD_C_CHECK(tc_pool_init_ex(&pool, sizeof(int), 1, &config));
    tc_handle first = tc_pool_alloc(&pool);
    GUARD_C_CHECK(first.index == 0);
    GUARD_C_CHECK(first.generation == 0);

    allocator.successful_allocations_before_failure = 2;
    GUARD_C_CHECK(tc_handle_is_invalid(tc_pool_alloc(&pool)));
    GUARD_C_CHECK(tc_pool_is_valid(&pool, first));
    GUARD_C_CHECK(pool.capacity == 1);

    allocator.successful_allocations_before_failure = 4;
    tc_handle second = tc_pool_alloc(&pool);
    GUARD_C_CHECK(second.index == 1);
    GUARD_C_CHECK(pool.capacity == 2);
    GUARD_C_CHECK(tc_handle_is_invalid(tc_pool_alloc(&pool)));
    GUARD_C_CHECK(pool.capacity == 2);
    tc_pool_free(&pool);

    tc_pool_generation_epoch epoch = {0};
    GUARD_C_CHECK(tc_pool_init_rebootstrap(&pool, sizeof(int), 1, &epoch));
    tc_handle before_rebootstrap = tc_pool_alloc(&pool);
    GUARD_C_CHECK(before_rebootstrap.index == 0);
    tc_pool_free(&pool);

    GUARD_C_CHECK(tc_pool_init_rebootstrap(&pool, sizeof(int), 1, &epoch));
    tc_handle after_rebootstrap = tc_pool_alloc(&pool);
    GUARD_C_CHECK(after_rebootstrap.index == before_rebootstrap.index);
    GUARD_C_CHECK(after_rebootstrap.generation > before_rebootstrap.generation);
    GUARD_C_CHECK(!tc_pool_is_valid(&pool, before_rebootstrap));

    GUARD_C_CHECK(tc_pool_free_slot(&pool, after_rebootstrap));
    tc_handle reused = tc_pool_alloc(&pool);
    GUARD_C_CHECK(reused.index == after_rebootstrap.index);
    GUARD_C_CHECK(reused.generation > after_rebootstrap.generation);
    tc_handle grown = tc_pool_alloc(&pool);
    GUARD_C_CHECK(grown.index != reused.index);
    tc_pool_free(&pool);

    GUARD_C_CHECK(tc_pool_init_rebootstrap(&pool, sizeof(int), 2, &epoch));
    tc_handle final_first = tc_pool_alloc(&pool);
    tc_handle final_second = tc_pool_alloc(&pool);
    GUARD_C_CHECK(!tc_pool_is_valid(&pool, reused));
    GUARD_C_CHECK(!tc_pool_is_valid(&pool, grown));
    GUARD_C_CHECK(final_first.generation > reused.generation);
    GUARD_C_CHECK(final_second.generation > grown.generation);
    tc_pool_free(&pool);
    return 0;
}
