// tc_runtime_type_registry.h - domain-agnostic runtime type records.
#ifndef TC_RUNTIME_TYPE_REGISTRY_H
#define TC_RUNTIME_TYPE_REGISTRY_H

#include "tc_types.h"
#include <tcbase/tc_dlist.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*tc_runtime_type_facet_destroy_fn)(void* payload);
typedef bool (*tc_runtime_type_facet_prepare_unload_fn)(
    const char* type_name,
    void* payload,
    void* context
);
typedef bool (*tc_runtime_type_iter_fn)(const char* type_name, void* user_data);
typedef bool (*tc_runtime_type_facet_iter_fn)(const char* facet_id, void* user_data);
typedef bool (*tc_runtime_type_instance_iter_fn)(
    void* instance,
    void* user_data
);

typedef struct tc_runtime_type_descriptor tc_runtime_type_descriptor;

typedef struct tc_runtime_type_instance_link {
    tc_dlist_node node;
    const char* type_name;
    uint64_t generation;
    void* instance;
} tc_runtime_type_instance_link;

typedef struct tc_runtime_type_record_info {
    const char* name;
    const char* owner;
    const char* parent;
    uint64_t generation;
    size_t facet_count;
    size_t instance_count;
    bool tombstoned;
} tc_runtime_type_record_info;

// Build one complete runtime type outside the live registry. The descriptor
// owns every facet payload accepted by add_facet. commit() consumes the
// descriptor on both success and failure.
TC_API tc_runtime_type_descriptor* tc_runtime_type_descriptor_create(
    const char* type_name,
    const char* owner,
    const char* parent_name
);
TC_API bool tc_runtime_type_descriptor_add_facet(
    tc_runtime_type_descriptor* descriptor,
    const char* facet_id,
    void* payload,
    tc_runtime_type_facet_destroy_fn destroy,
    tc_runtime_type_facet_prepare_unload_fn prepare_unload,
    uint32_t abi_version
);
// Permit this descriptor to replace an active ownerless shell. Callers must
// opt in only after verifying that the existing type carries no owned data.
TC_API bool tc_runtime_type_descriptor_allow_unowned_shell_adoption(
    tc_runtime_type_descriptor* descriptor
);
// Permit allocation-free replacement of an active descriptor owned by the
// same subsystem. Replacement is rejected while instances remain linked.
TC_API bool tc_runtime_type_descriptor_allow_same_owner_replacement(
    tc_runtime_type_descriptor* descriptor
);
TC_API void tc_runtime_type_descriptor_destroy(
    tc_runtime_type_descriptor* descriptor
);
TC_API bool tc_runtime_type_registry_commit_descriptor(
    tc_runtime_type_descriptor* descriptor
);

TC_API bool tc_runtime_type_registry_has_type(const char* type_name);
TC_API bool tc_runtime_type_registry_ensure_type(const char* type_name);
TC_API void tc_runtime_type_registry_unregister_type(const char* type_name);
TC_API bool tc_runtime_type_registry_unregister_type_with_context(
    const char* type_name,
    void* context
);
TC_API size_t tc_runtime_type_registry_unregister_owner(const char* owner);
TC_API size_t tc_runtime_type_registry_unregister_owner_with_context(
    const char* owner,
    void* context
);
TC_API bool tc_runtime_type_registry_prepare_owner_unload(
    const char* owner,
    void* context
);
TC_API bool tc_runtime_type_registry_commit_owner_unload(
    const char* owner,
    size_t* removed_count
);

TC_API bool tc_runtime_type_registry_set_owner(
    const char* type_name,
    const char* owner,
    bool allow_existing_unowned
);
TC_API const char* tc_runtime_type_registry_get_owner(const char* type_name);

TC_API bool tc_runtime_type_registry_set_parent(
    const char* type_name,
    const char* parent_name
);
TC_API const char* tc_runtime_type_registry_get_parent(const char* type_name);

TC_API bool tc_runtime_type_registry_set_facet(
    const char* type_name,
    const char* facet_id,
    void* payload,
    tc_runtime_type_facet_destroy_fn destroy,
    uint32_t abi_version
);
TC_API bool tc_runtime_type_registry_set_facet_with_lifecycle(
    const char* type_name,
    const char* facet_id,
    void* payload,
    tc_runtime_type_facet_destroy_fn destroy,
    tc_runtime_type_facet_prepare_unload_fn prepare_unload,
    uint32_t abi_version
);
TC_API void* tc_runtime_type_registry_get_facet(
    const char* type_name,
    const char* facet_id
);
TC_API bool tc_runtime_type_registry_remove_facet(
    const char* type_name,
    const char* facet_id
);
TC_API bool tc_runtime_type_registry_has_facet(
    const char* type_name,
    const char* facet_id
);
TC_API void tc_runtime_type_registry_foreach_type(
    tc_runtime_type_iter_fn callback,
    void* user_data
);
TC_API void tc_runtime_type_registry_foreach_type_with_facet(
    const char* facet_id,
    tc_runtime_type_iter_fn callback,
    void* user_data
);
TC_API void tc_runtime_type_registry_foreach_facet(
    const char* type_name,
    tc_runtime_type_facet_iter_fn callback,
    void* user_data
);

TC_API void tc_runtime_type_instance_link_init(tc_runtime_type_instance_link* link);
TC_API bool tc_runtime_type_registry_link_instance(
    const char* type_name,
    tc_runtime_type_instance_link* link,
    void* instance
);
TC_API void tc_runtime_type_registry_unlink_instance(
    tc_runtime_type_instance_link* link
);
TC_API size_t tc_runtime_type_registry_instance_count(const char* type_name);
TC_API bool tc_runtime_type_registry_instance_is_current(
    const tc_runtime_type_instance_link* link
);
TC_API void tc_runtime_type_registry_foreach_instance(
    const char* type_name,
    tc_runtime_type_instance_iter_fn callback,
    void* user_data
);

TC_API size_t tc_runtime_type_registry_types_with_facet_count(const char* facet_id);
TC_API const char* tc_runtime_type_registry_type_with_facet_at(
    const char* facet_id,
    size_t index
);

TC_API size_t tc_runtime_type_registry_type_count(void);
TC_API const char* tc_runtime_type_registry_type_at(size_t index);
TC_API bool tc_runtime_type_registry_get_info(
    const char* type_name,
    tc_runtime_type_record_info* out_info
);
TC_API size_t tc_runtime_type_registry_facet_count(const char* type_name);
TC_API const char* tc_runtime_type_registry_facet_at(
    const char* type_name,
    size_t index
);

TC_API void tc_runtime_type_registry_clear(void);

#ifdef __cplusplus
}
#endif

#endif // TC_RUNTIME_TYPE_REGISTRY_H
