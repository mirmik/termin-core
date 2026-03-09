// tc_inspect.c - Field inspection/serialization implementation
// C is a dispatcher only - routes calls to language-specific vtables
#include "inspect/tc_inspect.h"
#include "inspect/tc_kind.h"
#include <tcbase/tc_log.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

// Cross-platform strdup
#ifdef _WIN32
#define tc_strdup _strdup
#else
#define tc_strdup strdup
#endif

// tc_value implementation moved to termin-base (tcbase::termin_base).

// ============================================================================
// Parse parameterized kind
// ============================================================================

bool tc_kind_parse(const char* kind, char* container, size_t container_size,
                   char* element, size_t element_size) {
    if (!kind) return false;

    const char* bracket = strchr(kind, '[');
    if (!bracket) return false;

    const char* end_bracket = strrchr(kind, ']');
    if (!end_bracket || end_bracket <= bracket) return false;

    size_t container_len = bracket - kind;
    size_t element_len = end_bracket - bracket - 1;

    if (container_len >= container_size || element_len >= element_size) return false;

    strncpy(container, kind, container_len);
    container[container_len] = '\0';

    strncpy(element, bracket + 1, element_len);
    element[element_len] = '\0';

    return true;
}

// ============================================================================
// Language vtable dispatcher
// ============================================================================

static tc_inspect_lang_vtable g_vtables[TC_INSPECT_LANG_COUNT] = {0};

void tc_inspect_set_lang_vtable(tc_inspect_lang lang, const tc_inspect_lang_vtable* vtable) {
    if (lang >= 0 && lang < TC_INSPECT_LANG_COUNT && vtable) {
        g_vtables[lang] = *vtable;
    }
}

const tc_inspect_lang_vtable* tc_inspect_get_lang_vtable(tc_inspect_lang lang) {
    if (lang >= 0 && lang < TC_INSPECT_LANG_COUNT) {
        if (g_vtables[lang].has_type) {
            return &g_vtables[lang];
        }
    }
    return NULL;
}

// ============================================================================
// Type queries
// ============================================================================

bool tc_inspect_has_type(const char* type_name) {
    if (!type_name) return false;
    for (int i = 0; i < TC_INSPECT_LANG_COUNT; i++) {
        if (g_vtables[i].has_type && g_vtables[i].has_type(type_name, g_vtables[i].ctx)) {
            return true;
        }
    }
    return false;
}

tc_inspect_lang tc_inspect_type_lang(const char* type_name) {
    if (!type_name) return TC_INSPECT_LANG_COUNT;
    for (int i = 0; i < TC_INSPECT_LANG_COUNT; i++) {
        if (g_vtables[i].has_type && g_vtables[i].has_type(type_name, g_vtables[i].ctx)) {
            return (tc_inspect_lang)i;
        }
    }
    return TC_INSPECT_LANG_COUNT;
}

const char* tc_inspect_get_base_type(const char* type_name) {
    tc_inspect_lang lang = tc_inspect_type_lang(type_name);
    if (lang < TC_INSPECT_LANG_COUNT && g_vtables[lang].get_parent) {
        return g_vtables[lang].get_parent(type_name, g_vtables[lang].ctx);
    }
    return NULL;
}

// ============================================================================
// Field queries
// ============================================================================

size_t tc_inspect_field_count(const char* type_name) {
    tc_inspect_lang lang = tc_inspect_type_lang(type_name);
    if (lang < TC_INSPECT_LANG_COUNT && g_vtables[lang].field_count) {
        return g_vtables[lang].field_count(type_name, g_vtables[lang].ctx);
    }
    return 0;
}

bool tc_inspect_get_field_info(const char* type_name, size_t index, tc_field_info* out) {
    if (!out) return false;
    tc_inspect_lang lang = tc_inspect_type_lang(type_name);
    if (lang < TC_INSPECT_LANG_COUNT && g_vtables[lang].get_field) {
        return g_vtables[lang].get_field(type_name, index, out, g_vtables[lang].ctx);
    }
    return false;
}

bool tc_inspect_find_field_info(const char* type_name, const char* path, tc_field_info* out) {
    if (!out) return false;
    tc_inspect_lang lang = tc_inspect_type_lang(type_name);
    if (lang < TC_INSPECT_LANG_COUNT && g_vtables[lang].find_field) {
        return g_vtables[lang].find_field(type_name, path, out, g_vtables[lang].ctx);
    }
    return false;
}

// ============================================================================
// Field access
// ============================================================================

tc_value tc_inspect_get(void* obj, const char* type_name, const char* path) {
    tc_inspect_lang lang = tc_inspect_type_lang(type_name);
    if (lang >= TC_INSPECT_LANG_COUNT) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_get: type '%s' not found in any language vtable", type_name ? type_name : "null");
        return tc_value_nil();
    }
    if (!g_vtables[lang].get) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_get: no getter for type '%s' (lang=%d)", type_name ? type_name : "null", lang);
        return tc_value_nil();
    }
    return g_vtables[lang].get(obj, type_name, path, g_vtables[lang].ctx);
}

void tc_inspect_set(void* obj, const char* type_name, const char* path, tc_value value, void* context) {
    tc_inspect_lang lang = tc_inspect_type_lang(type_name);
    if (lang >= TC_INSPECT_LANG_COUNT) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_set: type '%s' not found in any language vtable", type_name ? type_name : "null");
        return;
    }
    if (!g_vtables[lang].set) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_set: no setter for type '%s' (lang=%d)", type_name ? type_name : "null", lang);
        return;
    }
    g_vtables[lang].set(obj, type_name, path, value, context, g_vtables[lang].ctx);
}

void tc_inspect_action(void* obj, const char* type_name, const char* path) {
    tc_inspect_lang lang = tc_inspect_type_lang(type_name);
    if (lang < TC_INSPECT_LANG_COUNT && g_vtables[lang].action) {
        g_vtables[lang].action(obj, type_name, path, g_vtables[lang].ctx);
    }
}

// ============================================================================
// Serialization
// ============================================================================

tc_value tc_inspect_serialize(void* obj, const char* type_name) {
    tc_value result = tc_value_dict_new();

    size_t count = tc_inspect_field_count(type_name);
    for (size_t i = 0; i < count; i++) {
        tc_field_info f;
        if (!tc_inspect_get_field_info(type_name, i, &f)) continue;
        if (!f.is_serializable) continue;

        tc_value val = tc_inspect_get(obj, type_name, f.path);
        if (val.type == TC_VALUE_NIL) continue;

        // Try tc_kind serialization
        if (tc_kind_exists(f.kind)) {
            tc_value serialized = tc_kind_serialize_any(f.kind, &val);
            if (serialized.type != TC_VALUE_NIL) {
                tc_value_dict_set(&result, f.path, serialized);
                tc_value_free(&val);
                continue;
            }
        }

        // No serializer - store value as-is
        tc_value_dict_set(&result, f.path, val);
    }

    return result;
}

void tc_inspect_deserialize(void* obj, const char* type_name, const tc_value* data, void* context) {
    if (!obj) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_deserialize: obj is NULL for type '%s'", type_name ? type_name : "unknown");
        return;
    }
    if (!type_name) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_deserialize: type_name is NULL");
        return;
    }
    if (!data) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_deserialize: data is NULL for type '%s'", type_name);
        return;
    }
    if (data->type != TC_VALUE_DICT) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_deserialize: data is not a dict for type '%s' (got type %d)", type_name, data->type);
        return;
    }

    size_t count = tc_inspect_field_count(type_name);
    if (count == 0) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_deserialize: no fields registered for type '%s'", type_name);
        return;
    }

    for (size_t i = 0; i < count; i++) {
        tc_field_info f;
        if (!tc_inspect_get_field_info(type_name, i, &f)) continue;
        if (!f.is_serializable) continue;

        tc_value* field_data = tc_value_dict_get((tc_value*)data, f.path);
        if (!field_data || field_data->type == TC_VALUE_NIL) continue;

        // Try tc_kind deserialization
        if (tc_kind_exists(f.kind)) {
            tc_value deserialized = tc_kind_deserialize_any(f.kind, field_data, context);
            if (deserialized.type != TC_VALUE_NIL) {
                tc_inspect_set(obj, type_name, f.path, deserialized, context);
                tc_value_free(&deserialized);
                continue;
            }
        }

        // No deserializer - set value as-is
        tc_inspect_set(obj, type_name, f.path, *field_data, context);
    }
}

// ============================================================================
// Cleanup
// ============================================================================

void tc_inspect_cleanup(void) {
    // Nothing to clean up - languages manage their own storage
    memset(g_vtables, 0, sizeof(g_vtables));
}
