// tc_pool.c - Generic object pool implementation
#include <tcbase/tc_pool.h>
#include <tcbase/tc_log.h>
#include <stdint.h>
#include <string.h>

// ============================================================================
// Internal helpers
// ============================================================================

static void* system_allocate(size_t size, void* user_data) {
    (void)user_data;
    return malloc(size);
}

static void system_deallocate(void* ptr, void* user_data) {
    (void)user_data;
    free(ptr);
}

static const char* pool_name(const tc_pool* pool) {
    return pool && pool->name && pool->name[0] ? pool->name : "tc_pool";
}

static bool allocation_size_valid(uint32_t capacity, size_t item_size) {
    return item_size != 0 && capacity <= SIZE_MAX / item_size;
}

static void pool_release_arrays(
    tc_pool_deallocate_fn deallocate,
    void* user_data,
    void* data,
    uint32_t* generations,
    uint8_t* states,
    uint32_t* free_list
) {
    if (data) deallocate(data, user_data);
    if (generations) deallocate(generations, user_data);
    if (states) deallocate(states, user_data);
    if (free_list) deallocate(free_list, user_data);
}

static void pool_append_free_range(
    tc_pool* pool,
    uint32_t* free_list,
    uint32_t first,
    uint32_t end,
    uint32_t* free_count
) {
    for (uint32_t i = first; i < end; ++i) {
        const uint32_t index = pool->allocate_low_indices_first
            ? end - 1u - (i - first)
            : i;
        free_list[(*free_count)++] = index;
    }
}

static void pool_advance_generation_epoch(tc_pool* pool) {
    tc_pool_generation_epoch* epoch = pool->generation_epoch;
    if (!epoch || pool->capacity == 0 || !pool->generations) return;

    uint32_t maximum = pool->generations[0];
    for (uint32_t i = 1; i < pool->capacity; ++i) {
        if (pool->generations[i] > maximum) maximum = pool->generations[i];
    }
    if (maximum == UINT32_MAX) {
        epoch->exhausted = true;
        tc_log_error(
            "[%s] handle generation epoch exhausted during shutdown",
            pool_name(pool)
        );
        return;
    }
    epoch->next_generation = maximum + 1u;
}

static void pool_release(tc_pool* pool, bool advance_epoch) {
    if (!pool) return;
    if (advance_epoch) pool_advance_generation_epoch(pool);

    tc_pool_deallocate_fn deallocate =
        pool->deallocate ? pool->deallocate : system_deallocate;
    pool_release_arrays(
        deallocate,
        pool->allocator_user_data,
        pool->data,
        pool->generations,
        pool->states,
        pool->free_list
    );
    memset(pool, 0, sizeof(*pool));
}

static bool pool_grow(tc_pool* pool, uint32_t requested_capacity) {
    const uint32_t old_capacity = pool->capacity;
    if (old_capacity >= pool->max_capacity) {
        tc_log_error("[%s] max capacity reached (%u)", pool_name(pool), pool->max_capacity);
        return false;
    }

    uint32_t new_capacity = requested_capacity;
    if (new_capacity == 0) {
        new_capacity = old_capacity == 0 ? 16u : old_capacity;
        if (new_capacity > UINT32_MAX / 2u) {
            new_capacity = UINT32_MAX;
        } else {
            new_capacity *= 2u;
        }
    }
    if (new_capacity > pool->max_capacity) new_capacity = pool->max_capacity;
    if (new_capacity <= old_capacity ||
        !allocation_size_valid(new_capacity, pool->item_size)) {
        tc_log_error("[%s] invalid pool growth capacity", pool_name(pool));
        return false;
    }

    void* data = pool->allocate(
        (size_t)new_capacity * pool->item_size,
        pool->allocator_user_data
    );
    uint32_t* generations = (uint32_t*)pool->allocate(
        (size_t)new_capacity * sizeof(uint32_t),
        pool->allocator_user_data
    );
    uint8_t* states = (uint8_t*)pool->allocate(
        (size_t)new_capacity * sizeof(uint8_t),
        pool->allocator_user_data
    );
    uint32_t* free_list = (uint32_t*)pool->allocate(
        (size_t)new_capacity * sizeof(uint32_t),
        pool->allocator_user_data
    );
    if (!data || !generations || !states || !free_list) {
        tc_log_error("[%s] grow allocation failed", pool_name(pool));
        pool_release_arrays(
            pool->deallocate,
            pool->allocator_user_data,
            data,
            generations,
            states,
            free_list
        );
        return false;
    }

    if (old_capacity != 0) {
        memcpy(data, pool->data, (size_t)old_capacity * pool->item_size);
        memcpy(
            generations,
            pool->generations,
            (size_t)old_capacity * sizeof(uint32_t)
        );
        memcpy(states, pool->states, (size_t)old_capacity * sizeof(uint8_t));
        memcpy(
            free_list,
            pool->free_list,
            (size_t)pool->free_count * sizeof(uint32_t)
        );
    }
    memset(
        (char*)data + (size_t)old_capacity * pool->item_size,
        0,
        (size_t)(new_capacity - old_capacity) * pool->item_size
    );
    memset(states + old_capacity, TC_SLOT_FREE, new_capacity - old_capacity);
    for (uint32_t i = old_capacity; i < new_capacity; ++i) {
        generations[i] = pool->initial_generation;
    }
    uint32_t free_count = pool->free_count;
    pool_append_free_range(
        pool,
        free_list,
        old_capacity,
        new_capacity,
        &free_count
    );

    pool_release_arrays(
        pool->deallocate,
        pool->allocator_user_data,
        pool->data,
        pool->generations,
        pool->states,
        pool->free_list
    );
    pool->data = data;
    pool->generations = generations;
    pool->states = states;
    pool->free_list = free_list;
    pool->capacity = new_capacity;
    pool->free_count = free_count;
    return true;
}

// ============================================================================
// Lifecycle
// ============================================================================

bool tc_pool_init(tc_pool* pool, size_t item_size, uint32_t initial_capacity) {
    const tc_pool_config config = {
        .max_capacity = UINT32_MAX,
        .initial_generation = 1u,
        .allocate_low_indices_first = false,
        .name = "tc_pool",
        .allocate = NULL,
        .deallocate = NULL,
        .allocator_user_data = NULL,
        .generation_epoch = NULL,
    };
    return tc_pool_init_ex(pool, item_size, initial_capacity, &config);
}

bool tc_pool_init_rebootstrap(
    tc_pool* pool,
    size_t item_size,
    uint32_t initial_capacity,
    tc_pool_generation_epoch* generation_epoch
) {
    const tc_pool_config config = {
        .max_capacity = UINT32_MAX,
        .initial_generation = 1u,
        .allocate_low_indices_first = false,
        .name = "tc_pool",
        .allocate = NULL,
        .deallocate = NULL,
        .allocator_user_data = NULL,
        .generation_epoch = generation_epoch,
    };
    return tc_pool_init_ex(pool, item_size, initial_capacity, &config);
}

bool tc_pool_init_ex(
    tc_pool* pool,
    size_t item_size,
    uint32_t initial_capacity,
    const tc_pool_config* config
) {
    if (!pool || item_size == 0) return false;

    const uint32_t max_capacity =
        config && config->max_capacity ? config->max_capacity : UINT32_MAX;
    if (initial_capacity > max_capacity ||
        !allocation_size_valid(initial_capacity, item_size)) {
        tc_log_error("[tc_pool] invalid initial or maximum capacity");
        memset(pool, 0, sizeof(*pool));
        return false;
    }
    if (config && ((config->allocate == NULL) != (config->deallocate == NULL))) {
        tc_log_error("[tc_pool] allocator and deallocator must be provided together");
        memset(pool, 0, sizeof(*pool));
        return false;
    }
    tc_pool_generation_epoch* generation_epoch =
        config ? config->generation_epoch : NULL;
    if (generation_epoch && generation_epoch->exhausted) {
        tc_log_error("[tc_pool] handle generation epoch is exhausted");
        memset(pool, 0, sizeof(*pool));
        return false;
    }

    memset(pool, 0, sizeof(*pool));
    pool->item_size = item_size;
    pool->max_capacity = max_capacity;
    const uint32_t configured_initial_generation =
        config ? config->initial_generation : 1u;
    if (generation_epoch && !generation_epoch->initialized) {
        generation_epoch->next_generation = configured_initial_generation;
        generation_epoch->initialized = true;
    }
    pool->initial_generation = generation_epoch
        ? generation_epoch->next_generation
        : configured_initial_generation;
    pool->allocate_low_indices_first =
        config ? config->allocate_low_indices_first : false;
    pool->name = config ? config->name : "tc_pool";
    pool->allocate = config && config->allocate ? config->allocate : system_allocate;
    pool->deallocate =
        config && config->deallocate ? config->deallocate : system_deallocate;
    pool->allocator_user_data = config ? config->allocator_user_data : NULL;
    pool->generation_epoch = generation_epoch;

    if (initial_capacity == 0) return true;
    if (!pool_grow(pool, initial_capacity)) {
        pool_release(pool, false);
        return false;
    }
    return true;
}

void tc_pool_free(tc_pool* pool) {
    pool_release(pool, true);
}

void tc_pool_clear(tc_pool* pool) {
    if (!pool) return;

    // Bump all generations and mark as free
    for (uint32_t i = 0; i < pool->capacity; i++) {
        if (pool->states[i] == TC_SLOT_OCCUPIED) {
            if (pool->generations[i] == UINT32_MAX) {
                pool->states[i] = TC_SLOT_RETIRED;
                tc_log_error(
                    "[%s] retired slot %u after handle generation exhaustion",
                    pool_name(pool),
                    i
                );
            } else {
                pool->generations[i]++;
                pool->states[i] = TC_SLOT_FREE;
            }
        }
    }

    // Rebuild free list
    pool->free_count = 0;
    for (uint32_t i = 0; i < pool->capacity; i++) {
        if (pool->states[i] == TC_SLOT_FREE) {
            pool->free_list[pool->free_count++] = i;
        }
    }

    pool->count = 0;
}

// ============================================================================
// Operations
// ============================================================================

tc_handle tc_pool_alloc(tc_pool* pool) {
    if (!pool) return TC_HANDLE_INVALID;

    // Grow if no free slots
    if (pool->free_count == 0) {
        if (!pool_grow(pool, 0)) {
            return TC_HANDLE_INVALID;
        }
    }

    // Pop from free list
    uint32_t index = pool->free_list[--pool->free_count];
    pool->states[index] = TC_SLOT_OCCUPIED;
    pool->count++;

    // Zero-init the slot data
    memset((char*)pool->data + index * pool->item_size, 0, pool->item_size);

    tc_handle h;
    h.index = index;
    h.generation = pool->generations[index];
    return h;
}

bool tc_pool_free_slot(tc_pool* pool, tc_handle h) {
    if (!pool) return false;
    if (h.index >= pool->capacity) return false;
    if (pool->states[h.index] != TC_SLOT_OCCUPIED) return false;
    if (pool->generations[h.index] != h.generation) return false;

    if (pool->generations[h.index] == UINT32_MAX) {
        pool->states[h.index] = TC_SLOT_RETIRED;
        tc_log_error(
            "[%s] retired slot %u after handle generation exhaustion",
            pool_name(pool),
            h.index
        );
    } else {
        pool->states[h.index] = TC_SLOT_FREE;
        pool->generations[h.index]++;
    }
    pool->count--;

    if (pool->states[h.index] == TC_SLOT_FREE) {
        pool->free_list[pool->free_count++] = h.index;
    }

    return true;
}

bool tc_pool_is_valid(const tc_pool* pool, tc_handle h) {
    if (!pool) return false;
    if (h.index >= pool->capacity) return false;
    if (pool->states[h.index] != TC_SLOT_OCCUPIED) return false;
    if (pool->generations[h.index] != h.generation) return false;
    return true;
}

void* tc_pool_get(const tc_pool* pool, tc_handle h) {
    if (!tc_pool_is_valid(pool, h)) return NULL;
    return (char*)pool->data + h.index * pool->item_size;
}

void* tc_pool_get_checked(const tc_pool* pool, tc_handle h, const char* resource_type) {
    void* item = tc_pool_get(pool, h);
    if (item) return item;

    if (pool && h.index < pool->capacity && pool->generations[h.index] != h.generation) {
        tc_log_error(
            "stale resource handle dereference: type=%s index=%u generation=%u current_generation=%u",
            resource_type && resource_type[0] ? resource_type : "unknown",
            h.index,
            h.generation,
            pool->generations[h.index]
        );
    }
    return NULL;
}

// ============================================================================
// Iteration
// ============================================================================

void tc_pool_foreach(tc_pool* pool, tc_pool_iter_fn callback, void* user_data) {
    if (!pool || !callback) return;

    for (uint32_t i = 0; i < pool->capacity; i++) {
        if (pool->states[i] == TC_SLOT_OCCUPIED) {
            void* item = (char*)pool->data + i * pool->item_size;
            if (!callback(i, item, user_data)) {
                break;
            }
        }
    }
}
