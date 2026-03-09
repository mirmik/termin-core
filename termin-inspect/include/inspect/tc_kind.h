// tc_kind.h - Language-agnostic kind serialization system
// C acts as a dispatcher; each language manages its own registry.
#pragma once

#include "tc_types.h"
#include "inspect/tc_inspect.h"

#ifdef __cplusplus
extern "C" {
#endif

// Language identifiers
typedef enum {
    TC_KIND_LANG_C = 0,
    TC_KIND_LANG_CPP = 1,
    TC_KIND_LANG_PYTHON = 2,
    TC_KIND_LANG_RUST = 3,
    TC_KIND_LANG_CSHARP = 4,
    TC_KIND_LANG_COUNT = 5
} tc_kind_lang;

// ============================================================================
// Language Registry Vtable
// Each language provides these callbacks to handle its kinds
// ============================================================================

// Check if kind exists in this language's registry
typedef bool (*tc_kind_has_fn)(const char* kind_name, void* ctx);

// Serialize a value (language-specific logic)
typedef tc_value (*tc_kind_serialize_fn)(const char* kind_name, const tc_value* input, void* ctx);

// Deserialize a value (language-specific logic)
typedef tc_value (*tc_kind_deserialize_fn)(const char* kind_name, const tc_value* input, void* context, void* ctx);

// Get list of all kinds in this language's registry
typedef size_t (*tc_kind_list_fn)(const char** out_names, size_t max_count, void* ctx);

// Language registry vtable
typedef struct {
    tc_kind_has_fn has;
    tc_kind_serialize_fn serialize;
    tc_kind_deserialize_fn deserialize;
    tc_kind_list_fn list;
    void* ctx;
} tc_kind_lang_registry;

// ============================================================================
// Registry Management
// ============================================================================

// Register a language's registry vtable
TC_API void tc_kind_set_lang_registry(tc_kind_lang lang, const tc_kind_lang_registry* registry);

// Get a language's registry (returns NULL if not set)
TC_API const tc_kind_lang_registry* tc_kind_get_lang_registry(tc_kind_lang lang);

// ============================================================================
// Query API - delegates to language registries
// ============================================================================

// Check if kind exists in any language
TC_API bool tc_kind_exists(const char* name);

// Check if kind exists in specific language
TC_API bool tc_kind_has_lang(const char* name, tc_kind_lang lang);

// Serialize using specified language's handler
TC_API tc_value tc_kind_serialize(const char* name, tc_kind_lang lang, const tc_value* input);

// Deserialize using specified language's handler
TC_API tc_value tc_kind_deserialize(const char* name, tc_kind_lang lang, const tc_value* input, void* context);

// Find first available language handler and serialize
TC_API tc_value tc_kind_serialize_any(const char* name, const tc_value* input);

// Find first available language handler and deserialize
TC_API tc_value tc_kind_deserialize_any(const char* name, const tc_value* input, void* context);

// Get all registered kind names (from all languages, deduplicated)
TC_API size_t tc_kind_list_all(const char** out_names, size_t max_count);

// Cleanup (clears registry pointers, does NOT free language-side data)
TC_API void tc_kind_cleanup(void);

#ifdef __cplusplus
}
#endif
