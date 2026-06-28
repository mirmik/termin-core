#include "inspect/tc_runtime_type_registry.h"

#include <tcbase/tc_log.h>
#include <tcbase/tc_resource_map.h>
#include <tcbase/tgfx_intern_string.h>

#include <stdlib.h>
#include <string.h>

typedef struct tc_runtime_type_facet_record {
    void* payload;
    tc_runtime_type_facet_destroy_fn destroy;
    uint32_t abi_version;
} tc_runtime_type_facet_record;

typedef struct tc_runtime_type_record {
    const char* name;
    const char* owner;
    const char* parent;
    uint64_t generation;
    tc_resource_map* facets;
} tc_runtime_type_record;

typedef struct tc_runtime_type_registry_storage {
    tc_resource_map* records;
    const char* current_owner;
} tc_runtime_type_registry_storage;

static tc_runtime_type_registry_storage g_runtime_type_registry = {0};

static void destroy_facet_record(void* payload) {
    tc_runtime_type_facet_record* facet = (tc_runtime_type_facet_record*)payload;
    if (!facet) {
        return;
    }
    if (facet->destroy && facet->payload) {
        facet->destroy(facet->payload);
    }
    free(facet);
}

static void destroy_type_record(void* payload) {
    tc_runtime_type_record* record = (tc_runtime_type_record*)payload;
    if (!record) {
        return;
    }
    if (record->facets) {
        tc_resource_map_free(record->facets);
    }
    free(record);
}

static void ensure_registry_initialized(void) {
    if (!g_runtime_type_registry.records) {
        g_runtime_type_registry.records = tc_resource_map_new(destroy_type_record);
    }
}

static tc_runtime_type_record* find_record(const char* type_name) {
    if (!type_name || !g_runtime_type_registry.records) {
        return NULL;
    }
    return (tc_runtime_type_record*)tc_resource_map_get(
        g_runtime_type_registry.records,
        type_name
    );
}

static tc_runtime_type_record* ensure_record(const char* type_name) {
    if (!type_name || !type_name[0]) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] cannot create unnamed runtime type");
        return NULL;
    }

    ensure_registry_initialized();

    tc_runtime_type_record* record = find_record(type_name);
    if (record) {
        return record;
    }

    record = (tc_runtime_type_record*)calloc(1, sizeof(tc_runtime_type_record));
    if (!record) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] failed to allocate type '%s'", type_name);
        return NULL;
    }

    record->name = tgfx_intern_string(type_name);
    record->owner = g_runtime_type_registry.current_owner;
    record->parent = NULL;
    record->generation = 1;
    record->facets = tc_resource_map_new(destroy_facet_record);
    if (!record->facets) {
        free(record);
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] failed to allocate facets for '%s'", type_name);
        return NULL;
    }

    if (!tc_resource_map_add(g_runtime_type_registry.records, record->name, record)) {
        tc_resource_map_free(record->facets);
        free(record);
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] failed to insert type '%s'", type_name);
        return NULL;
    }

    return record;
}

void tc_runtime_type_registry_set_registration_owner(const char* owner) {
    g_runtime_type_registry.current_owner =
        (owner && owner[0]) ? tgfx_intern_string(owner) : NULL;
}

const char* tc_runtime_type_registry_get_registration_owner(void) {
    return g_runtime_type_registry.current_owner;
}

bool tc_runtime_type_registry_has_type(const char* type_name) {
    return find_record(type_name) != NULL;
}

bool tc_runtime_type_registry_ensure_type(const char* type_name) {
    return ensure_record(type_name) != NULL;
}

void tc_runtime_type_registry_unregister_type(const char* type_name) {
    if (!type_name || !g_runtime_type_registry.records) {
        return;
    }
    tc_resource_map_remove(g_runtime_type_registry.records, type_name);
}

typedef struct unregister_owner_ctx {
    const char* owner;
    const char** names;
    size_t count;
    size_t capacity;
} unregister_owner_ctx;

static bool collect_owner_type(const char* name, void* resource, void* user_data) {
    (void)name;
    unregister_owner_ctx* ctx = (unregister_owner_ctx*)user_data;
    tc_runtime_type_record* record = (tc_runtime_type_record*)resource;
    if (!ctx || !record || !record->owner || strcmp(record->owner, ctx->owner) != 0) {
        return true;
    }

    if (ctx->count >= ctx->capacity) {
        size_t new_capacity = ctx->capacity == 0 ? 8 : ctx->capacity * 2;
        const char** new_names = (const char**)realloc(
            ctx->names,
            new_capacity * sizeof(const char*)
        );
        if (!new_names) {
            tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] failed to grow owner cleanup list");
            return false;
        }
        ctx->names = new_names;
        ctx->capacity = new_capacity;
    }

    ctx->names[ctx->count++] = record->name;
    return true;
}

size_t tc_runtime_type_registry_unregister_owner(const char* owner) {
    if (!owner || !owner[0] || !g_runtime_type_registry.records) {
        return 0;
    }

    unregister_owner_ctx ctx = {
        tgfx_intern_string(owner),
        NULL,
        0,
        0
    };
    tc_resource_map_foreach(g_runtime_type_registry.records, collect_owner_type, &ctx);

    for (size_t i = 0; i < ctx.count; ++i) {
        tc_resource_map_remove(g_runtime_type_registry.records, ctx.names[i]);
    }

    size_t removed = ctx.count;
    free(ctx.names);
    return removed;
}

bool tc_runtime_type_registry_set_owner(
    const char* type_name,
    const char* owner,
    bool allow_existing_unowned
) {
    if (!type_name || !type_name[0]) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] cannot set owner for unnamed runtime type");
        return false;
    }
    if (!owner || !owner[0]) {
        return true;
    }

    tc_runtime_type_record* record = ensure_record(type_name);
    if (!record) {
        return false;
    }

    const char* interned_owner = tgfx_intern_string(owner);
    if (!record->owner) {
        if (!allow_existing_unowned) {
            return false;
        }
        record->owner = interned_owner;
        record->generation++;
        return true;
    }
    if (strcmp(record->owner, interned_owner) == 0) {
        return true;
    }

    tc_log(
        TC_LOG_WARN,
        "[RuntimeTypeRegistry] owner conflict for type '%s': existing='%s' incoming='%s'",
        type_name,
        record->owner,
        interned_owner
    );
    return false;
}

const char* tc_runtime_type_registry_get_owner(const char* type_name) {
    tc_runtime_type_record* record = find_record(type_name);
    return record ? record->owner : NULL;
}

bool tc_runtime_type_registry_set_parent(const char* type_name, const char* parent_name) {
    if (!type_name || !type_name[0]) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] cannot set parent for unnamed runtime type");
        return false;
    }

    tc_runtime_type_record* record = ensure_record(type_name);
    if (!record) {
        return false;
    }

    const char* parent = (parent_name && parent_name[0])
        ? tgfx_intern_string(parent_name)
        : NULL;
    if (record->parent == parent ||
        (record->parent && parent && strcmp(record->parent, parent) == 0)) {
        return true;
    }

    record->parent = parent;
    record->generation++;
    return true;
}

const char* tc_runtime_type_registry_get_parent(const char* type_name) {
    tc_runtime_type_record* record = find_record(type_name);
    return record ? record->parent : NULL;
}

bool tc_runtime_type_registry_set_facet(
    const char* type_name,
    const char* facet_id,
    void* payload,
    tc_runtime_type_facet_destroy_fn destroy,
    uint32_t abi_version
) {
    if (!type_name || !type_name[0] || !facet_id || !facet_id[0]) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] cannot set unnamed facet or type");
        return false;
    }

    tc_runtime_type_record* record = ensure_record(type_name);
    if (!record) {
        return false;
    }

    tc_runtime_type_facet_record* existing =
        (tc_runtime_type_facet_record*)tc_resource_map_get(record->facets, facet_id);
    if (existing && existing->payload == payload && existing->destroy == destroy) {
        existing->abi_version = abi_version;
        record->generation++;
        return true;
    }

    if (existing) {
        tc_resource_map_remove(record->facets, facet_id);
    }

    tc_runtime_type_facet_record* facet =
        (tc_runtime_type_facet_record*)calloc(1, sizeof(tc_runtime_type_facet_record));
    if (!facet) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] failed to allocate facet '%s.%s'", type_name, facet_id);
        return false;
    }
    facet->payload = payload;
    facet->destroy = destroy;
    facet->abi_version = abi_version;

    if (!tc_resource_map_add(record->facets, facet_id, facet)) {
        free(facet);
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] failed to insert facet '%s.%s'", type_name, facet_id);
        return false;
    }

    record->generation++;
    return true;
}

void* tc_runtime_type_registry_get_facet(const char* type_name, const char* facet_id) {
    tc_runtime_type_record* record = find_record(type_name);
    if (!record || !facet_id) {
        return NULL;
    }
    tc_runtime_type_facet_record* facet =
        (tc_runtime_type_facet_record*)tc_resource_map_get(record->facets, facet_id);
    return facet ? facet->payload : NULL;
}

bool tc_runtime_type_registry_remove_facet(const char* type_name, const char* facet_id) {
    tc_runtime_type_record* record = find_record(type_name);
    if (!record || !facet_id) {
        return false;
    }

    if (!tc_resource_map_remove(record->facets, facet_id)) {
        return false;
    }

    if (tc_resource_map_count(record->facets) == 0) {
        tc_resource_map_remove(g_runtime_type_registry.records, type_name);
        return true;
    }

    record->generation++;
    return true;
}

bool tc_runtime_type_registry_has_facet(const char* type_name, const char* facet_id) {
    tc_runtime_type_record* record = find_record(type_name);
    return record && facet_id && tc_resource_map_contains(record->facets, facet_id);
}

typedef struct foreach_type_with_facet_ctx {
    const char* facet_id;
    tc_runtime_type_iter_fn callback;
    void* user_data;
} foreach_type_with_facet_ctx;

typedef struct foreach_type_ctx {
    tc_runtime_type_iter_fn callback;
    void* user_data;
} foreach_type_ctx;

static bool foreach_type_ctx_bridge(const char* name, void* resource, void* user_data) {
    (void)name;
    foreach_type_ctx* ctx = (foreach_type_ctx*)user_data;
    tc_runtime_type_record* record = (tc_runtime_type_record*)resource;
    return ctx->callback(record->name, ctx->user_data);
}

void tc_runtime_type_registry_foreach_type(
    tc_runtime_type_iter_fn callback,
    void* user_data
) {
    if (!callback || !g_runtime_type_registry.records) {
        return;
    }
    foreach_type_ctx ctx = { callback, user_data };
    tc_resource_map_foreach(g_runtime_type_registry.records, foreach_type_ctx_bridge, &ctx);
}

static bool foreach_type_with_facet_bridge(const char* name, void* resource, void* user_data) {
    (void)name;
    foreach_type_with_facet_ctx* ctx = (foreach_type_with_facet_ctx*)user_data;
    tc_runtime_type_record* record = (tc_runtime_type_record*)resource;
    if (!record || !tc_resource_map_contains(record->facets, ctx->facet_id)) {
        return true;
    }
    return ctx->callback(record->name, ctx->user_data);
}

void tc_runtime_type_registry_foreach_type_with_facet(
    const char* facet_id,
    tc_runtime_type_iter_fn callback,
    void* user_data
) {
    if (!facet_id || !callback || !g_runtime_type_registry.records) {
        return;
    }
    foreach_type_with_facet_ctx ctx = { facet_id, callback, user_data };
    tc_resource_map_foreach(g_runtime_type_registry.records, foreach_type_with_facet_bridge, &ctx);
}

typedef struct foreach_facet_ctx {
    tc_runtime_type_facet_iter_fn callback;
    void* user_data;
} foreach_facet_ctx;

static bool foreach_facet_bridge(const char* facet_id, void* resource, void* user_data) {
    (void)resource;
    foreach_facet_ctx* ctx = (foreach_facet_ctx*)user_data;
    return ctx->callback(facet_id, ctx->user_data);
}

void tc_runtime_type_registry_foreach_facet(
    const char* type_name,
    tc_runtime_type_facet_iter_fn callback,
    void* user_data
) {
    tc_runtime_type_record* record = find_record(type_name);
    if (!record || !callback) {
        return;
    }
    foreach_facet_ctx ctx = { callback, user_data };
    tc_resource_map_foreach(record->facets, foreach_facet_bridge, &ctx);
}

typedef struct count_ctx {
    size_t count;
} count_ctx;

static bool count_type_cb(const char* type_name, void* user_data) {
    (void)type_name;
    ((count_ctx*)user_data)->count++;
    return true;
}

size_t tc_runtime_type_registry_types_with_facet_count(const char* facet_id) {
    count_ctx ctx = {0};
    tc_runtime_type_registry_foreach_type_with_facet(facet_id, count_type_cb, &ctx);
    return ctx.count;
}

typedef struct type_at_ctx {
    size_t target;
    size_t current;
    const char* result;
} type_at_ctx;

static bool type_at_cb(const char* type_name, void* user_data) {
    type_at_ctx* ctx = (type_at_ctx*)user_data;
    if (ctx->current == ctx->target) {
        ctx->result = type_name;
        return false;
    }
    ctx->current++;
    return true;
}

const char* tc_runtime_type_registry_type_with_facet_at(
    const char* facet_id,
    size_t index
) {
    type_at_ctx ctx = { index, 0, NULL };
    tc_runtime_type_registry_foreach_type_with_facet(facet_id, type_at_cb, &ctx);
    return ctx.result;
}

size_t tc_runtime_type_registry_type_count(void) {
    return g_runtime_type_registry.records
        ? tc_resource_map_count(g_runtime_type_registry.records)
        : 0;
}

const char* tc_runtime_type_registry_type_at(size_t index) {
    type_at_ctx ctx = { index, 0, NULL };
    tc_runtime_type_registry_foreach_type(type_at_cb, &ctx);
    return ctx.result;
}

bool tc_runtime_type_registry_get_info(
    const char* type_name,
    tc_runtime_type_record_info* out_info
) {
    tc_runtime_type_record* record = find_record(type_name);
    if (!record || !out_info) {
        return false;
    }

    out_info->name = record->name;
    out_info->owner = record->owner;
    out_info->parent = record->parent;
    out_info->generation = record->generation;
    out_info->facet_count = tc_resource_map_count(record->facets);
    return true;
}

size_t tc_runtime_type_registry_facet_count(const char* type_name) {
    tc_runtime_type_record* record = find_record(type_name);
    return record ? tc_resource_map_count(record->facets) : 0;
}

typedef struct facet_at_ctx {
    size_t target;
    size_t current;
    const char* result;
} facet_at_ctx;

static bool facet_at_cb(const char* facet_id, void* user_data) {
    facet_at_ctx* ctx = (facet_at_ctx*)user_data;
    if (ctx->current == ctx->target) {
        ctx->result = facet_id;
        return false;
    }
    ctx->current++;
    return true;
}

const char* tc_runtime_type_registry_facet_at(const char* type_name, size_t index) {
    facet_at_ctx ctx = { index, 0, NULL };
    tc_runtime_type_registry_foreach_facet(type_name, facet_at_cb, &ctx);
    return ctx.result;
}

void tc_runtime_type_registry_clear(void) {
    if (g_runtime_type_registry.records) {
        tc_resource_map_free(g_runtime_type_registry.records);
        g_runtime_type_registry.records = NULL;
    }
    g_runtime_type_registry.current_owner = NULL;
}
