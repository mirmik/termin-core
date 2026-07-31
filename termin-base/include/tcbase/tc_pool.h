// tc_pool.h - Generic object pool with generation tracking
#pragma once

#include <tcbase/tcbase_api.h>
#include <tcbase/tc_binding_types.h>
#include <stdlib.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Pool slot state
// ============================================================================

#define TC_SLOT_FREE     0
#define TC_SLOT_OCCUPIED 1
#define TC_SLOT_RETIRED  2

// Persistent state owned by a registry whose pool can be destroyed and
// recreated while old public handles may still exist. Zero-initialization is
// valid; tc_pool_init_ex publishes the configured initial generation on first
// use and tc_pool_free advances it beyond every generation used by that pool.
typedef struct tc_pool_generation_epoch {
    uint32_t next_generation;
    bool initialized;
    bool exhausted;
} tc_pool_generation_epoch;

// ============================================================================
// Generic pool structure
// ============================================================================

typedef struct tc_pool {
    void* data;              // Array of items (type-specific)
    uint32_t* generations;   // Generation per slot
    uint8_t* states;         // TC_SLOT_FREE or TC_SLOT_OCCUPIED
    uint32_t* free_list;     // Indices of free slots
    uint32_t capacity;       // Total slots
    uint32_t count;          // Occupied slots
    uint32_t free_count;     // Free slots in free_list
    size_t item_size;        // Size of each item
    uint32_t max_capacity;   // Hard slot limit (UINT32_MAX when unbounded)
    uint32_t initial_generation;
    bool allocate_low_indices_first;
    const char* name;
    void* (*allocate)(size_t size, void* user_data);
    void (*deallocate)(void* ptr, void* user_data);
    void* allocator_user_data;
    tc_pool_generation_epoch* generation_epoch;
} tc_pool;

typedef void* (*tc_pool_allocate_fn)(size_t size, void* user_data);
typedef void (*tc_pool_deallocate_fn)(void* ptr, void* user_data);

typedef struct tc_pool_config {
    uint32_t max_capacity;  // 0 means UINT32_MAX.
    uint32_t initial_generation;
    bool allocate_low_indices_first;
    const char* name;
    tc_pool_allocate_fn allocate;
    tc_pool_deallocate_fn deallocate;
    void* allocator_user_data;
    tc_pool_generation_epoch* generation_epoch;
} tc_pool_config;

// ============================================================================
// Pool lifecycle
// ============================================================================

// Initialize pool with given item size and initial capacity
TCBASE_API bool tc_pool_init(tc_pool* pool, size_t item_size, uint32_t initial_capacity);

// Initialize a process-lifetime registry pool whose handles must remain stale
// across tc_pool_free() followed by another initialization with the same epoch.
TCBASE_API bool tc_pool_init_rebootstrap(
    tc_pool* pool,
    size_t item_size,
    uint32_t initial_capacity,
    tc_pool_generation_epoch* generation_epoch
);

// Initialize a configured pool. Custom allocation is transactional: init/grow
// either publishes all replacement arrays or leaves the pool unchanged.
TCBASE_API bool tc_pool_init_ex(
    tc_pool* pool,
    size_t item_size,
    uint32_t initial_capacity,
    const tc_pool_config* config
);

// Free pool resources
TCBASE_API void tc_pool_free(tc_pool* pool);

// Clear pool (mark all as free, bump generations)
TCBASE_API void tc_pool_clear(tc_pool* pool);

// ============================================================================
// Pool operations
// ============================================================================

// Allocate a new slot, returns handle (or TC_HANDLE_INVALID on failure)
TCBASE_API tc_handle tc_pool_alloc(tc_pool* pool);

// Free a slot by handle (returns true if freed, false if invalid handle)
TCBASE_API bool tc_pool_free_slot(tc_pool* pool, tc_handle h);

// Check if handle is valid (correct generation, occupied)
TCBASE_API bool tc_pool_is_valid(const tc_pool* pool, tc_handle h);

// Get pointer to item by handle (returns NULL if invalid)
TCBASE_API void* tc_pool_get(const tc_pool* pool, tc_handle h);

// Resolve a handle at a public dereference boundary. Unlike tc_pool_get(),
// this reports an invalid/stale handle with the resource type and handle
// coordinates. Deliberate probes must keep using tc_pool_is_valid().
TCBASE_API void* tc_pool_get_checked(
    const tc_pool* pool,
    tc_handle h,
    const char* resource_type
);

// Get pointer to item by index (no validation - use carefully!)
static inline void* tc_pool_get_unchecked(const tc_pool* pool, uint32_t index) {
    return (char*)pool->data + index * pool->item_size;
}

// ============================================================================
// Pool iteration
// ============================================================================

// Iterator callback: receives index, item pointer, user_data
// Return true to continue, false to stop
typedef bool (*tc_pool_iter_fn)(uint32_t index, void* item, void* user_data);

// Iterate over all occupied slots
TCBASE_API void tc_pool_foreach(tc_pool* pool, tc_pool_iter_fn callback, void* user_data);

// Get count of occupied slots
static inline uint32_t tc_pool_count(const tc_pool* pool) {
    return pool ? pool->count : 0;
}

#ifdef __cplusplus
}
#endif
