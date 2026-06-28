// tc_runtime_type_registry.h - domain-agnostic runtime type records.
#ifndef TC_RUNTIME_TYPE_REGISTRY_H
#define TC_RUNTIME_TYPE_REGISTRY_H

#include "tc_types.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*tc_runtime_type_facet_destroy_fn)(void* payload);
typedef bool (*tc_runtime_type_iter_fn)(const char* type_name, void* user_data);
typedef bool (*tc_runtime_type_facet_iter_fn)(const char* facet_id, void* user_data);

typedef struct tc_runtime_type_record_info {
    const char* name;
    const char* owner;
    const char* parent;
    uint64_t generation;
    size_t facet_count;
} tc_runtime_type_record_info;

TC_API void tc_runtime_type_registry_set_registration_owner(const char* owner);
TC_API const char* tc_runtime_type_registry_get_registration_owner(void);

TC_API bool tc_runtime_type_registry_has_type(const char* type_name);
TC_API bool tc_runtime_type_registry_ensure_type(const char* type_name);
TC_API void tc_runtime_type_registry_unregister_type(const char* type_name);
TC_API size_t tc_runtime_type_registry_unregister_owner(const char* owner);

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
