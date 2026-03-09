// tc_inspect.h - Generic field inspection/serialization dispatcher
// C is a dispatcher only. Each language manages its own type/field storage.
// Domain-specific adapter APIs are declared in separate adapter headers.
#ifndef TC_INSPECT_H
#define TC_INSPECT_H

#include "tc_value.h"
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Language enum - which language owns the type/field
// ============================================================================

typedef enum tc_inspect_lang {
    TC_INSPECT_LANG_C = 0,
    TC_INSPECT_LANG_CPP = 1,
    TC_INSPECT_LANG_PYTHON = 2,
    TC_INSPECT_LANG_CSHARP = 3,
    TC_INSPECT_LANG_COUNT = 4
} tc_inspect_lang;

// ============================================================================
// Field info - metadata for one inspectable field
// Language owns the memory, C just passes pointers through
// ============================================================================

typedef struct tc_enum_choice {
    int value;
    const char* label;
} tc_enum_choice;

typedef struct tc_field_info {
    const char* path;           // Field path ("mesh", "transform.position")
    const char* label;          // Display label
    const char* kind;           // "bool", "float", "mesh_handle", "list[entity_handle]"

    // Numeric constraints (for "int", "float", "double")
    double min;
    double max;
    double step;

    // Flags
    bool is_serializable;   // Include in serialization (default true)
    bool is_inspectable;    // Show in inspector (default true)

    // For enum fields
    const tc_enum_choice* choices;
    size_t choice_count;
} tc_field_info;

// ============================================================================
// Language vtable - each language registers its implementation
// ============================================================================

// Callback types
typedef bool (*tc_inspect_has_type_fn)(const char* type_name, void* ctx);
typedef const char* (*tc_inspect_get_parent_fn)(const char* type_name, void* ctx);
typedef size_t (*tc_inspect_field_count_fn)(const char* type_name, void* ctx);
typedef bool (*tc_inspect_get_field_fn)(const char* type_name, size_t index, tc_field_info* out, void* ctx);
typedef bool (*tc_inspect_find_field_fn)(const char* type_name, const char* path, tc_field_info* out, void* ctx);
typedef tc_value (*tc_inspect_getter_fn)(void* obj, const char* type_name, const char* path, void* ctx);
typedef void (*tc_inspect_setter_fn)(void* obj, const char* type_name, const char* path, tc_value value, void* context, void* ctx);
typedef void (*tc_inspect_action_fn)(void* obj, const char* type_name, const char* path, void* ctx);

typedef struct tc_inspect_lang_vtable {
    tc_inspect_has_type_fn has_type;
    tc_inspect_get_parent_fn get_parent;
    tc_inspect_field_count_fn field_count;
    tc_inspect_get_field_fn get_field;
    tc_inspect_find_field_fn find_field;
    tc_inspect_getter_fn get;
    tc_inspect_setter_fn set;
    tc_inspect_action_fn action;
    void* ctx;
} tc_inspect_lang_vtable;

// ============================================================================
// Language registration
// ============================================================================

// Register language vtable
TC_API void tc_inspect_set_lang_vtable(tc_inspect_lang lang, const tc_inspect_lang_vtable* vtable);

// Get language vtable (returns NULL if not set)
TC_API const tc_inspect_lang_vtable* tc_inspect_get_lang_vtable(tc_inspect_lang lang);

// ============================================================================
// Type queries (dispatches to language that owns the type)
// ============================================================================

// Check if type exists in any language
TC_API bool tc_inspect_has_type(const char* type_name);

// Get which language owns this type (returns TC_INSPECT_LANG_COUNT if not found)
TC_API tc_inspect_lang tc_inspect_type_lang(const char* type_name);

// Get base type (returns NULL if no base)
TC_API const char* tc_inspect_get_base_type(const char* type_name);

// ============================================================================
// Field queries (dispatches to owning language)
// ============================================================================

// Count all fields including inherited
TC_API size_t tc_inspect_field_count(const char* type_name);

// Get field info by index (fills out, returns true if found)
TC_API bool tc_inspect_get_field_info(const char* type_name, size_t index, tc_field_info* out);

// Find field info by path (fills out, returns true if found)
TC_API bool tc_inspect_find_field_info(const char* type_name, const char* path, tc_field_info* out);

// ============================================================================
// Field access (dispatches to owning language)
// ============================================================================

TC_API tc_value tc_inspect_get(void* obj, const char* type_name, const char* path);
TC_API void tc_inspect_set(void* obj, const char* type_name, const char* path, tc_value value, void* context);
TC_API void tc_inspect_action(void* obj, const char* type_name, const char* path);

// ============================================================================
// Serialization (dispatches to owning language)
// ============================================================================

// Serialize all fields to dict (only is_serializable fields)
TC_API tc_value tc_inspect_serialize(void* obj, const char* type_name);

// Deserialize from dict with runtime context
TC_API void tc_inspect_deserialize(void* obj, const char* type_name, const tc_value* data, void* context);

// ============================================================================
// Parameterized kinds (e.g., "list[entity_handle]")
// ============================================================================

// Parse "list[T]" → ("list", "T"), returns false if not parameterized
TC_API bool tc_kind_parse(const char* kind, char* container, size_t container_size,
                          char* element, size_t element_size);

// ============================================================================
// JSON interop
// ============================================================================

TC_API char* tc_value_to_json(const tc_value* v);
TC_API tc_value tc_value_from_json(const char* json);

// ============================================================================
// Cleanup
// ============================================================================

TC_API void tc_inspect_cleanup(void);

#ifdef __cplusplus
}
#endif

#endif // TC_INSPECT_H
