#include "inspect/tc_runtime_type_registry.h"

#include <tcbase/tc_log.h>
#include <tcbase/tc_resource_map.h>
#include <tcbase/tc_string.h>

#include <stdlib.h>
#include <string.h>

typedef struct tc_runtime_type_facet_record {
    void* payload;
    tc_runtime_type_facet_destroy_fn destroy;
    tc_runtime_type_facet_prepare_unload_fn prepare_unload;
    uint32_t abi_version;
} tc_runtime_type_facet_record;

typedef struct tc_runtime_type_record {
    const char* name;
    const char* owner;
    const char* parent;
    uint64_t generation;
    tc_resource_map* facets;
    tc_dlist_head instances;
    size_t instance_count;
    bool tombstoned;
} tc_runtime_type_record;

typedef struct tc_runtime_type_registry_storage {
    tc_resource_map* records;
    const char* current_owner;
} tc_runtime_type_registry_storage;

static tc_runtime_type_registry_storage g_runtime_type_registry = {0};

static tc_runtime_type_record* find_record(const char* type_name);

static bool parent_assignment_is_acyclic(
    const char* type_name,
    const char* parent_name
) {
    if (!parent_name || !parent_name[0]) {
        return true;
    }

    const char* candidate = parent_name;
    size_t steps = 0;
    const size_t max_steps = tc_runtime_type_registry_type_count() + 1;
    while (candidate) {
        if (strcmp(candidate, type_name) == 0) {
            tc_log(
                TC_LOG_ERROR,
                "[RuntimeTypeRegistry] parent assignment rejected: cycle for type '%s' through parent '%s'",
                type_name,
                parent_name
            );
            return false;
        }
        if (steps++ >= max_steps) {
            tc_log(
                TC_LOG_ERROR,
                "[RuntimeTypeRegistry] parent assignment rejected: existing parent cycle while assigning type '%s' to parent '%s'",
                type_name,
                parent_name
            );
            return false;
        }

        tc_runtime_type_record* parent = find_record(candidate);
        if (!parent || parent->tombstoned) {
            return true;
        }
        candidate = parent->parent;
    }
    return true;
}

struct tc_runtime_type_descriptor {
    const char* name;
    const char* owner;
    const char* parent;
    tc_resource_map* facets;
    tc_runtime_type_record* prepared_record;
    char* prepared_record_key;
    bool allow_unowned_shell_adoption;
    bool allow_same_owner_replacement;
    bool valid;
};

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

    tc_dlist_node* pos = NULL;
    tc_dlist_node* tmp = NULL;
    tc_dlist_for_each_safe(pos, tmp, &record->instances) {
        tc_runtime_type_instance_link* link =
            tc_dlist_entry(pos, tc_runtime_type_instance_link, node);
        tc_dlist_del(&link->node);
        link->type_name = NULL;
        link->generation = 0;
        link->instance = NULL;
    }
    record->instance_count = 0;

    if (record->facets) {
        tc_resource_map_free(record->facets);
    }
    free(record);
}

static char* duplicate_string(const char* value) {
    if (!value) {
        return NULL;
    }
    size_t size = strlen(value) + 1;
    char* copy = (char*)malloc(size);
    if (copy) {
        memcpy(copy, value, size);
    }
    return copy;
}

static void ensure_registry_initialized(void) {
    if (!g_runtime_type_registry.records) {
        g_runtime_type_registry.records = tc_resource_map_new(destroy_type_record);
    }
}

static bool descriptor_parent_is_valid(const tc_runtime_type_descriptor* descriptor) {
    if (!descriptor->parent) {
        return true;
    }
    const char* candidate = descriptor->parent;
    size_t steps = 0;
    size_t max_steps = tc_runtime_type_registry_type_count() + 1;
    while (candidate) {
        if (steps++ >= max_steps) {
            tc_log(
                TC_LOG_ERROR,
                "[RuntimeTypeRegistry] descriptor rejected: existing parent cycle while committing type '%s' owner '%s'",
                descriptor->name,
                descriptor->owner
            );
            return false;
        }
        if (strcmp(candidate, descriptor->name) == 0) {
            tc_log(
                TC_LOG_ERROR,
                "[RuntimeTypeRegistry] descriptor rejected: parent cycle for type '%s' owner '%s'",
                descriptor->name,
                descriptor->owner
            );
            return false;
        }
        tc_runtime_type_record* parent = find_record(candidate);
        if (!parent || parent->tombstoned) {
            tc_log(
                TC_LOG_ERROR,
                "[RuntimeTypeRegistry] descriptor rejected: missing parent '%s' for type '%s' owner '%s'",
                candidate,
                descriptor->name,
                descriptor->owner
            );
            return false;
        }
        candidate = parent->parent;
    }
    return true;
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

tc_runtime_type_descriptor* tc_runtime_type_descriptor_create(
    const char* type_name,
    const char* owner,
    const char* parent_name
) {
    if (!type_name || !type_name[0] || !owner || !owner[0]) {
        tc_log(
            TC_LOG_ERROR,
            "[RuntimeTypeRegistry] descriptor requires non-empty type and explicit owner"
        );
        return NULL;
    }

    tc_runtime_type_descriptor* descriptor =
        (tc_runtime_type_descriptor*)calloc(1, sizeof(tc_runtime_type_descriptor));
    if (!descriptor) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] failed to allocate descriptor for '%s'", type_name);
        return NULL;
    }
    descriptor->name = tc_intern_string(type_name);
    descriptor->owner = tc_intern_string(owner);
    descriptor->parent = (parent_name && parent_name[0])
        ? tc_intern_string(parent_name)
        : NULL;
    descriptor->facets = tc_resource_map_new(destroy_facet_record);
    descriptor->prepared_record =
        (tc_runtime_type_record*)calloc(1, sizeof(tc_runtime_type_record));
    descriptor->prepared_record_key = duplicate_string(type_name);
    descriptor->valid = descriptor->name && descriptor->owner &&
        (!(parent_name && parent_name[0]) || descriptor->parent) &&
        descriptor->facets && descriptor->prepared_record && descriptor->prepared_record_key;

    ensure_registry_initialized();
    if (!g_runtime_type_registry.records ||
        !tc_resource_map_reserve(g_runtime_type_registry.records, 1)) {
        descriptor->valid = false;
    }
    if (!descriptor->valid) {
        tc_log(
            TC_LOG_ERROR,
            "[RuntimeTypeRegistry] failed to preallocate descriptor for type '%s' owner '%s'",
            type_name,
            owner
        );
        tc_runtime_type_descriptor_destroy(descriptor);
        return NULL;
    }
    return descriptor;
}

bool tc_runtime_type_descriptor_add_facet(
    tc_runtime_type_descriptor* descriptor,
    const char* facet_id,
    void* payload,
    tc_runtime_type_facet_destroy_fn destroy,
    tc_runtime_type_facet_prepare_unload_fn prepare_unload,
    uint32_t abi_version
) {
    if (!descriptor || !descriptor->valid || !facet_id || !facet_id[0] || abi_version == 0) {
        tc_log(
            TC_LOG_ERROR,
            "[RuntimeTypeRegistry] descriptor facet rejected: type='%s' owner='%s' facet='%s' abi=%u",
            descriptor && descriptor->name ? descriptor->name : "<unknown>",
            descriptor && descriptor->owner ? descriptor->owner : "<unknown>",
            facet_id ? facet_id : "<unknown>",
            abi_version
        );
        if (destroy && payload) {
            destroy(payload);
        }
        if (descriptor) {
            descriptor->valid = false;
        }
        return false;
    }
    if (tc_resource_map_contains(descriptor->facets, facet_id)) {
        tc_log(
            TC_LOG_ERROR,
            "[RuntimeTypeRegistry] duplicate descriptor facet: type='%s' owner='%s' facet='%s'",
            descriptor->name,
            descriptor->owner,
            facet_id
        );
        if (destroy && payload) {
            destroy(payload);
        }
        descriptor->valid = false;
        return false;
    }

    tc_runtime_type_facet_record* facet =
        (tc_runtime_type_facet_record*)calloc(1, sizeof(tc_runtime_type_facet_record));
    if (!facet) {
        tc_log(
            TC_LOG_ERROR,
            "[RuntimeTypeRegistry] failed to allocate descriptor facet '%s.%s' owner '%s'",
            descriptor->name,
            facet_id,
            descriptor->owner
        );
        if (destroy && payload) {
            destroy(payload);
        }
        descriptor->valid = false;
        return false;
    }
    facet->payload = payload;
    facet->destroy = destroy;
    facet->prepare_unload = prepare_unload;
    facet->abi_version = abi_version;
    if (!tc_resource_map_add(descriptor->facets, facet_id, facet)) {
        destroy_facet_record(facet);
        tc_log(
            TC_LOG_ERROR,
            "[RuntimeTypeRegistry] failed to stage descriptor facet '%s.%s' owner '%s'",
            descriptor->name,
            facet_id,
            descriptor->owner
        );
        descriptor->valid = false;
        return false;
    }
    return true;
}

bool tc_runtime_type_descriptor_allow_unowned_shell_adoption(
    tc_runtime_type_descriptor* descriptor
) {
    if (!descriptor || !descriptor->valid) {
        tc_log(
            TC_LOG_ERROR,
            "[RuntimeTypeRegistry] cannot enable shell adoption on an invalid descriptor"
        );
        return false;
    }
    descriptor->allow_unowned_shell_adoption = true;
    return true;
}

bool tc_runtime_type_descriptor_allow_same_owner_replacement(
    tc_runtime_type_descriptor* descriptor
) {
    if (!descriptor || !descriptor->valid) {
        tc_log(
            TC_LOG_ERROR,
            "[RuntimeTypeRegistry] cannot enable same-owner replacement on an invalid descriptor"
        );
        return false;
    }
    descriptor->allow_same_owner_replacement = true;
    return true;
}

void tc_runtime_type_descriptor_destroy(tc_runtime_type_descriptor* descriptor) {
    if (!descriptor) {
        return;
    }
    if (descriptor->facets) {
        tc_resource_map_free(descriptor->facets);
    }
    free(descriptor->prepared_record);
    free(descriptor->prepared_record_key);
    free(descriptor);
}

bool tc_runtime_type_registry_commit_descriptor(
    tc_runtime_type_descriptor* descriptor
) {
    if (!descriptor) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] cannot commit a null descriptor");
        return false;
    }

    bool committed = false;
    tc_runtime_type_record* existing = find_record(descriptor->name);
    const bool can_adopt_unowned_shell =
        existing && !existing->tombstoned &&
        descriptor->allow_unowned_shell_adoption &&
        !existing->owner && existing->instance_count == 0;
    const bool can_replace_same_owner =
        existing && !existing->tombstoned &&
        descriptor->allow_same_owner_replacement &&
        existing->owner && strcmp(existing->owner, descriptor->owner) == 0 &&
        existing->instance_count == 0;
    if (!descriptor->valid || !descriptor_parent_is_valid(descriptor)) {
        tc_log(
            TC_LOG_ERROR,
            "[RuntimeTypeRegistry] descriptor commit rejected: type='%s' owner='%s'",
            descriptor->name,
            descriptor->owner
        );
    } else if (existing && !existing->tombstoned &&
               !can_adopt_unowned_shell && !can_replace_same_owner) {
        tc_log(
            TC_LOG_ERROR,
            "[RuntimeTypeRegistry] active descriptor replacement rejected: type='%s' existing_owner='%s' incoming_owner='%s'",
            descriptor->name,
            existing->owner ? existing->owner : "<none>",
            descriptor->owner
        );
    } else if (can_adopt_unowned_shell || can_replace_same_owner) {
        tc_resource_map* replaced_facets = existing->facets;
        existing->owner = descriptor->owner;
        existing->parent = descriptor->parent;
        existing->facets = descriptor->facets;
        existing->generation++;
        descriptor->facets = NULL;
        if (replaced_facets) {
            tc_resource_map_free(replaced_facets);
        }
        committed = true;
    } else if (existing &&
               (!existing->owner || strcmp(existing->owner, descriptor->owner) != 0)) {
        tc_log(
            TC_LOG_ERROR,
            "[RuntimeTypeRegistry] tombstone owner conflict: type='%s' existing_owner='%s' incoming_owner='%s'",
            descriptor->name,
            existing->owner ? existing->owner : "<none>",
            descriptor->owner
        );
    } else if (existing) {
        tc_resource_map* replaced_facets = existing->facets;
        existing->owner = descriptor->owner;
        existing->parent = descriptor->parent;
        existing->facets = descriptor->facets;
        existing->tombstoned = false;
        existing->generation++;
        descriptor->facets = NULL;
        if (replaced_facets) {
            tc_resource_map_free(replaced_facets);
        }
        committed = true;
    } else {
        tc_runtime_type_record* record = descriptor->prepared_record;
        record->name = descriptor->name;
        record->owner = descriptor->owner;
        record->parent = descriptor->parent;
        record->generation = 1;
        record->facets = descriptor->facets;
        tc_dlist_init_head(&record->instances);
        record->instance_count = 0;
        record->tombstoned = false;
        if (tc_resource_map_add_owned_key(
                g_runtime_type_registry.records,
                descriptor->prepared_record_key,
                record
            )) {
            descriptor->prepared_record = NULL;
            descriptor->prepared_record_key = NULL;
            descriptor->facets = NULL;
            committed = true;
        } else {
            record->facets = NULL;
            tc_log(
                TC_LOG_ERROR,
                "[RuntimeTypeRegistry] allocation-free descriptor publication failed: type='%s' owner='%s'",
                descriptor->name,
                descriptor->owner
            );
        }
    }

    tc_runtime_type_descriptor_destroy(descriptor);
    return committed;
}

static tc_runtime_type_record* ensure_record(const char* type_name) {
    if (!type_name || !type_name[0]) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] cannot create unnamed runtime type");
        return NULL;
    }

    ensure_registry_initialized();

    tc_runtime_type_record* record = find_record(type_name);
    if (record) {
        if (record->tombstoned) {
            record->tombstoned = false;
            record->generation++;
        }
        return record;
    }

    record = (tc_runtime_type_record*)calloc(1, sizeof(tc_runtime_type_record));
    if (!record) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] failed to allocate type '%s'", type_name);
        return NULL;
    }

    record->name = tc_intern_string(type_name);
    record->owner = g_runtime_type_registry.current_owner;
    record->parent = NULL;
    record->generation = 1;
    record->facets = tc_resource_map_new(destroy_facet_record);
    tc_dlist_init_head(&record->instances);
    record->instance_count = 0;
    record->tombstoned = false;
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

static void clear_record_facets(tc_runtime_type_record* record) {
    if (!record || !record->facets) {
        return;
    }

    tc_resource_map_free(record->facets);
    record->facets = tc_resource_map_new(destroy_facet_record);
    if (!record->facets) {
        tc_log(
            TC_LOG_ERROR,
            "[RuntimeTypeRegistry] failed to recreate facets for tombstoned type '%s'",
            record->name ? record->name : "<unknown>"
        );
    }
}

static void try_remove_tombstoned_record(tc_runtime_type_record* record) {
    if (!record || !record->name || !g_runtime_type_registry.records) {
        return;
    }
    if (!record->tombstoned) {
        return;
    }
    if (record->instance_count > 0) {
        return;
    }
    if (record->facets && tc_resource_map_count(record->facets) > 0) {
        return;
    }

    tc_resource_map_remove(g_runtime_type_registry.records, record->name);
}

typedef struct prepare_unload_ctx {
    const char* type_name;
    void* context;
    bool ok;
} prepare_unload_ctx;

static bool prepare_facet_unload_bridge(
    const char* facet_id,
    void* resource,
    void* user_data
) {
    prepare_unload_ctx* ctx = (prepare_unload_ctx*)user_data;
    tc_runtime_type_facet_record* facet = (tc_runtime_type_facet_record*)resource;
    if (!ctx || !facet || !facet->prepare_unload) {
        return true;
    }

    if (!facet->prepare_unload(ctx->type_name, facet->payload, ctx->context)) {
        tc_log(
            TC_LOG_ERROR,
            "[RuntimeTypeRegistry] facet '%s' refused unload for runtime type '%s'",
            facet_id ? facet_id : "<unknown>",
            ctx->type_name ? ctx->type_name : "<unknown>"
        );
        ctx->ok = false;
        return false;
    }
    return true;
}

static bool prepare_record_unload(tc_runtime_type_record* record, void* context) {
    if (!record || !record->facets) {
        return true;
    }

    prepare_unload_ctx ctx = { record->name, context, true };
    tc_resource_map_foreach(record->facets, prepare_facet_unload_bridge, &ctx);
    return ctx.ok;
}

void tc_runtime_type_registry_set_registration_owner(const char* owner) {
    g_runtime_type_registry.current_owner =
        (owner && owner[0]) ? tc_intern_string(owner) : NULL;
}

const char* tc_runtime_type_registry_get_registration_owner(void) {
    return g_runtime_type_registry.current_owner;
}

bool tc_runtime_type_registry_has_type(const char* type_name) {
    tc_runtime_type_record* record = find_record(type_name);
    return record && !record->tombstoned;
}

bool tc_runtime_type_registry_ensure_type(const char* type_name) {
    return ensure_record(type_name) != NULL;
}

bool tc_runtime_type_registry_unregister_type_with_context(
    const char* type_name,
    void* context
) {
    if (!type_name || !g_runtime_type_registry.records) {
        return true;
    }

    tc_runtime_type_record* record = find_record(type_name);
    if (!record) {
        return true;
    }

    if (!prepare_record_unload(record, context)) {
        return false;
    }

    if (record->instance_count == 0) {
        tc_resource_map_remove(g_runtime_type_registry.records, type_name);
        return true;
    }

    clear_record_facets(record);
    record->tombstoned = true;
    record->generation++;
    return true;
}

void tc_runtime_type_registry_unregister_type(const char* type_name) {
    (void)tc_runtime_type_registry_unregister_type_with_context(type_name, NULL);
}

typedef struct unregister_owner_ctx {
    const char* owner;
    const char** names;
    size_t count;
    size_t capacity;
    bool ok;
} unregister_owner_ctx;

static bool collect_owner_type(const char* name, void* resource, void* user_data) {
    (void)name;
    unregister_owner_ctx* ctx = (unregister_owner_ctx*)user_data;
    tc_runtime_type_record* record = (tc_runtime_type_record*)resource;
    if (!ctx || !record || record->tombstoned ||
        !record->owner || strcmp(record->owner, ctx->owner) != 0) {
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
            ctx->ok = false;
            return false;
        }
        ctx->names = new_names;
        ctx->capacity = new_capacity;
    }

    ctx->names[ctx->count++] = record->name;
    return true;
}

static unregister_owner_ctx collect_owner_types(const char* owner) {
    unregister_owner_ctx ctx = {
        tc_intern_string(owner),
        NULL,
        0,
        0,
        true
    };
    tc_resource_map_foreach(g_runtime_type_registry.records, collect_owner_type, &ctx);
    return ctx;
}

bool tc_runtime_type_registry_prepare_owner_unload(
    const char* owner,
    void* context
) {
    if (!owner || !owner[0] || !g_runtime_type_registry.records) {
        return true;
    }

    unregister_owner_ctx ctx = collect_owner_types(owner);
    if (!ctx.ok) {
        free(ctx.names);
        return false;
    }

    for (size_t i = 0; i < ctx.count; ++i) {
        tc_runtime_type_record* record = find_record(ctx.names[i]);
        if (record && !prepare_record_unload(record, context)) {
            free(ctx.names);
            return false;
        }
    }

    free(ctx.names);
    return true;
}

bool tc_runtime_type_registry_commit_owner_unload(
    const char* owner,
    size_t* removed_count
) {
    if (removed_count) {
        *removed_count = 0;
    }
    if (!owner || !owner[0] || !g_runtime_type_registry.records) {
        return true;
    }

    unregister_owner_ctx ctx = collect_owner_types(owner);
    if (!ctx.ok) {
        free(ctx.names);
        return false;
    }

    size_t removed = 0;
    for (size_t i = 0; i < ctx.count; ++i) {
        tc_runtime_type_record* record = find_record(ctx.names[i]);
        if (!record) {
            continue;
        }
        if (record->instance_count == 0) {
            tc_resource_map_remove(g_runtime_type_registry.records, ctx.names[i]);
        } else {
            clear_record_facets(record);
            record->tombstoned = true;
            record->generation++;
        }
        removed++;
    }

    free(ctx.names);
    if (removed_count) {
        *removed_count = removed;
    }
    return true;
}

size_t tc_runtime_type_registry_unregister_owner_with_context(
    const char* owner,
    void* context
) {
    if (!tc_runtime_type_registry_prepare_owner_unload(owner, context)) {
        return 0;
    }
    size_t removed = 0;
    if (!tc_runtime_type_registry_commit_owner_unload(owner, &removed)) {
        return 0;
    }
    return removed;
}

size_t tc_runtime_type_registry_unregister_owner(const char* owner) {
    return tc_runtime_type_registry_unregister_owner_with_context(owner, NULL);
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

    const char* interned_owner = tc_intern_string(owner);
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

    if (!parent_assignment_is_acyclic(type_name, parent_name)) {
        return false;
    }

    const char* parent = (parent_name && parent_name[0])
        ? tc_intern_string(parent_name)
        : NULL;
    tc_runtime_type_record* record = ensure_record(type_name);
    if (!record) {
        return false;
    }
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
    return tc_runtime_type_registry_set_facet_with_lifecycle(
        type_name,
        facet_id,
        payload,
        destroy,
        NULL,
        abi_version
    );
}

bool tc_runtime_type_registry_set_facet_with_lifecycle(
    const char* type_name,
    const char* facet_id,
    void* payload,
    tc_runtime_type_facet_destroy_fn destroy,
    tc_runtime_type_facet_prepare_unload_fn prepare_unload,
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
    if (!record->facets) {
        record->facets = tc_resource_map_new(destroy_facet_record);
        if (!record->facets) {
            tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] failed to allocate facets for '%s'", type_name);
            return false;
        }
    }

    tc_runtime_type_facet_record* existing =
        (tc_runtime_type_facet_record*)tc_resource_map_get(record->facets, facet_id);
    if (existing && existing->payload == payload &&
        existing->destroy == destroy &&
        existing->prepare_unload == prepare_unload) {
        existing->abi_version = abi_version;
        record->generation++;
        return true;
    }

    tc_runtime_type_facet_record* facet =
        (tc_runtime_type_facet_record*)calloc(1, sizeof(tc_runtime_type_facet_record));
    if (!facet) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] failed to allocate facet '%s.%s'", type_name, facet_id);
        return false;
    }
    facet->payload = payload;
    facet->destroy = destroy;
    facet->prepare_unload = prepare_unload;
    facet->abi_version = abi_version;

    if (!tc_resource_map_replace(record->facets, facet_id, facet)) {
        free(facet);
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] failed to publish facet '%s.%s'", type_name, facet_id);
        return false;
    }

    record->generation++;
    return true;
}

void* tc_runtime_type_registry_get_facet(const char* type_name, const char* facet_id) {
    tc_runtime_type_record* record = find_record(type_name);
    if (!record || !record->facets || !facet_id) {
        return NULL;
    }
    tc_runtime_type_facet_record* facet =
        (tc_runtime_type_facet_record*)tc_resource_map_get(record->facets, facet_id);
    return facet ? facet->payload : NULL;
}

bool tc_runtime_type_registry_remove_facet(const char* type_name, const char* facet_id) {
    tc_runtime_type_record* record = find_record(type_name);
    if (!record || !record->facets || !facet_id) {
        return false;
    }

    if (!tc_resource_map_remove(record->facets, facet_id)) {
        return false;
    }

    if (tc_resource_map_count(record->facets) == 0 && record->instance_count == 0) {
        tc_resource_map_remove(g_runtime_type_registry.records, type_name);
        return true;
    }

    if (tc_resource_map_count(record->facets) == 0) {
        record->tombstoned = true;
    }
    record->generation++;
    return true;
}

bool tc_runtime_type_registry_has_facet(const char* type_name, const char* facet_id) {
    tc_runtime_type_record* record = find_record(type_name);
    return record && record->facets && facet_id &&
        tc_resource_map_contains(record->facets, facet_id);
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
    if (!record || !record->facets ||
        !tc_resource_map_contains(record->facets, ctx->facet_id)) {
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
    if (!record || !record->facets || !callback) {
        return;
    }
    foreach_facet_ctx ctx = { callback, user_data };
    tc_resource_map_foreach(record->facets, foreach_facet_bridge, &ctx);
}

void tc_runtime_type_instance_link_init(tc_runtime_type_instance_link* link) {
    if (!link) {
        return;
    }
    tc_dlist_init_node(&link->node);
    link->type_name = NULL;
    link->generation = 0;
    link->instance = NULL;
}

bool tc_runtime_type_registry_link_instance(
    const char* type_name,
    tc_runtime_type_instance_link* link,
    void* instance
) {
    if (!type_name || !type_name[0] || !link || !instance) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] cannot link unnamed runtime instance");
        return false;
    }

    if (tc_dlist_is_linked(&link->node)) {
        tc_runtime_type_registry_unlink_instance(link);
    } else {
        tc_dlist_init_node(&link->node);
    }

    tc_runtime_type_record* record = find_record(type_name);
    if (!record) {
        record = ensure_record(type_name);
    }
    if (!record) {
        return false;
    }
    if (record->tombstoned) {
        tc_log(
            TC_LOG_ERROR,
            "[RuntimeTypeRegistry] cannot link instance to tombstoned runtime type '%s'",
            type_name
        );
        return false;
    }

    link->type_name = record->name;
    link->generation = record->generation;
    link->instance = instance;
    tc_dlist_add_tail(&link->node, &record->instances);
    record->instance_count++;
    return true;
}

void tc_runtime_type_registry_unlink_instance(tc_runtime_type_instance_link* link) {
    if (!link || !link->type_name) {
        return;
    }

    const char* type_name = link->type_name;
    tc_runtime_type_record* record = find_record(type_name);
    if (record && tc_dlist_is_linked(&link->node)) {
        tc_dlist_del(&link->node);
        if (record->instance_count > 0) {
            record->instance_count--;
        }
    } else if (tc_dlist_is_linked(&link->node)) {
        tc_dlist_del(&link->node);
    }

    link->type_name = NULL;
    link->generation = 0;
    link->instance = NULL;

    if (record) {
        try_remove_tombstoned_record(record);
    }
}

size_t tc_runtime_type_registry_instance_count(const char* type_name) {
    tc_runtime_type_record* record = find_record(type_name);
    return record ? record->instance_count : 0;
}

bool tc_runtime_type_registry_instance_is_current(
    const tc_runtime_type_instance_link* link
) {
    if (!link || !link->type_name) {
        return false;
    }
    tc_runtime_type_record* record = find_record(link->type_name);
    return record && !record->tombstoned && record->generation == link->generation;
}

void tc_runtime_type_registry_foreach_instance(
    const char* type_name,
    tc_runtime_type_instance_iter_fn callback,
    void* user_data
) {
    tc_runtime_type_record* record = find_record(type_name);
    if (!record || !callback) {
        return;
    }

    tc_dlist_node* pos = NULL;
    tc_dlist_node* tmp = NULL;
    tc_dlist_for_each_safe(pos, tmp, &record->instances) {
        tc_runtime_type_instance_link* link =
            tc_dlist_entry(pos, tc_runtime_type_instance_link, node);
        if (!callback(link->instance, user_data)) {
            return;
        }
    }
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
    out_info->facet_count = record->facets ? tc_resource_map_count(record->facets) : 0;
    out_info->instance_count = record->instance_count;
    out_info->tombstoned = record->tombstoned;
    return true;
}

size_t tc_runtime_type_registry_facet_count(const char* type_name) {
    tc_runtime_type_record* record = find_record(type_name);
    return (record && record->facets) ? tc_resource_map_count(record->facets) : 0;
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
