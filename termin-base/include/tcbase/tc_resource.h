// tc_resource.h - Common resource header for mesh, texture, etc.
#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include "tc_log.h"
#include "tc_uuid.h"

#ifdef __cplusplus
extern "C" {
#endif

// Process-wide bridge from native resource registries to the canonical asset
// runtime. UUIDs are globally unique, so resource types do not participate in
// lazy-load routing.
typedef bool (*tc_resource_loader_fn)(const char* uuid, void* user_data);

TCBASE_API void tc_resource_set_loader(
    tc_resource_loader_fn callback,
    void* user_data
);
TCBASE_API void tc_resource_clear_loader(void);
TCBASE_API bool tc_resource_request_load(const char* uuid);

// ============================================================================
// Resource header - common fields for all resources
// ============================================================================
// Place this as the FIRST field in resource structs for consistent layout.

typedef struct tc_resource_header {
    char uuid[TC_UUID_SIZE];        // unique identifier
    const char* name;               // human-readable name (interned string)
    uint32_t version;               // incremented on data change (for GPU sync)
    uint32_t ref_count;             // reference count for ownership
    uint32_t pool_index;            // index in resource pool (for GPUContext lookup)
    uint8_t is_loaded;              // true if data is loaded
    uint8_t _pad[3];
} tc_resource_header;

// ============================================================================
// Resource header helpers
// ============================================================================

// Initialize resource header with UUID
static inline void tc_resource_copy_uuid(
    char* dst,
    size_t dst_size,
    const char* uuid,
    const char* context
) {
    if (!dst || dst_size == 0) return;
    if (uuid && uuid[0] != '\0') {
        size_t len = strlen(uuid);
        if (len >= dst_size) {
            tc_log_warn(
                "%s: UUID '%s' is too long (%zu bytes), truncating to %u bytes",
                context && context[0] ? context : "tc_resource_copy_uuid",
                uuid,
                len,
                (unsigned)(dst_size - 1)
            );
            len = dst_size - 1;
        }
        memcpy(dst, uuid, len);
        dst[len] = '\0';
    } else {
        dst[0] = '\0';
    }
}

static inline void tc_resource_header_set_uuid(
    tc_resource_header* header,
    const char* uuid,
    const char* context
) {
    if (!header) return;
    tc_resource_copy_uuid(header->uuid, sizeof(header->uuid), uuid, context);
}

// Initialize resource header with UUID
static inline void tc_resource_header_init(tc_resource_header* header, const char* uuid) {
    tc_resource_header_set_uuid(header, uuid, "tc_resource_header_init");
    header->name = NULL;
    header->version = 1;
    header->ref_count = 0;
    header->pool_index = 0;
    header->is_loaded = 0;
}

// Trigger process-wide UUID loading when the resource is not loaded.
static inline bool tc_resource_header_ensure_loaded(tc_resource_header* header) {
    if (header->is_loaded) return true;

    bool success = tc_resource_request_load(header->uuid);
    if (success) {
        header->is_loaded = 1;
    }
    return success;
}

// Bump version (call after data change)
static inline void tc_resource_header_bump_version(tc_resource_header* header) {
    header->version++;
}

#ifdef __cplusplus
}
#endif
