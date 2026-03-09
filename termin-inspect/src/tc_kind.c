// tc_kind.c - Kind registry dispatcher implementation
// C acts only as access point; each language manages its own registry.
#include "inspect/tc_kind.h"
#include <string.h>

// Language registry vtables
static tc_kind_lang_registry g_registries[TC_KIND_LANG_COUNT] = {0};

void tc_kind_set_lang_registry(tc_kind_lang lang, const tc_kind_lang_registry* registry) {
    if (lang < 0 || lang >= TC_KIND_LANG_COUNT || !registry) {
        return;
    }
    g_registries[lang] = *registry;
}

const tc_kind_lang_registry* tc_kind_get_lang_registry(tc_kind_lang lang) {
    if (lang < 0 || lang >= TC_KIND_LANG_COUNT) {
        return NULL;
    }
    if (!g_registries[lang].has) {
        return NULL;
    }
    return &g_registries[lang];
}

bool tc_kind_exists(const char* name) {
    if (!name) return false;

    for (int i = 0; i < TC_KIND_LANG_COUNT; i++) {
        if (g_registries[i].has) {
            if (g_registries[i].has(name, g_registries[i].ctx)) {
                return true;
            }
        }
    }
    return false;
}

bool tc_kind_has_lang(const char* name, tc_kind_lang lang) {
    if (!name || lang < 0 || lang >= TC_KIND_LANG_COUNT) {
        return false;
    }
    if (!g_registries[lang].has) {
        return false;
    }
    return g_registries[lang].has(name, g_registries[lang].ctx);
}

tc_value tc_kind_serialize(const char* name, tc_kind_lang lang, const tc_value* input) {
    if (!name || !input || lang < 0 || lang >= TC_KIND_LANG_COUNT) {
        return tc_value_nil();
    }
    if (!g_registries[lang].serialize) {
        return tc_value_nil();
    }
    return g_registries[lang].serialize(name, input, g_registries[lang].ctx);
}

tc_value tc_kind_deserialize(const char* name, tc_kind_lang lang, const tc_value* input, void* context) {
    if (!name || !input || lang < 0 || lang >= TC_KIND_LANG_COUNT) {
        return tc_value_nil();
    }
    if (!g_registries[lang].deserialize) {
        return tc_value_nil();
    }
    return g_registries[lang].deserialize(name, input, context, g_registries[lang].ctx);
}

tc_value tc_kind_serialize_any(const char* name, const tc_value* input) {
    if (!name || !input) {
        return tc_value_nil();
    }

    // Try each language in order
    for (int i = 0; i < TC_KIND_LANG_COUNT; i++) {
        if (g_registries[i].has && g_registries[i].serialize) {
            if (g_registries[i].has(name, g_registries[i].ctx)) {
                return g_registries[i].serialize(name, input, g_registries[i].ctx);
            }
        }
    }
    return tc_value_nil();
}

tc_value tc_kind_deserialize_any(const char* name, const tc_value* input, void* context) {
    if (!name || !input) {
        return tc_value_nil();
    }

    // Try each language in order
    for (int i = 0; i < TC_KIND_LANG_COUNT; i++) {
        if (g_registries[i].has && g_registries[i].deserialize) {
            if (g_registries[i].has(name, g_registries[i].ctx)) {
                return g_registries[i].deserialize(name, input, context, g_registries[i].ctx);
            }
        }
    }
    return tc_value_nil();
}

size_t tc_kind_list_all(const char** out_names, size_t max_count) {
    // For simplicity, just collect from all languages
    // Note: this doesn't deduplicate, caller should handle that if needed
    size_t total = 0;

    for (int i = 0; i < TC_KIND_LANG_COUNT; i++) {
        if (g_registries[i].list) {
            size_t remaining = max_count > total ? max_count - total : 0;
            const char** dest = out_names ? out_names + total : NULL;
            size_t count = g_registries[i].list(dest, remaining, g_registries[i].ctx);
            total += count;
        }
    }

    return total;
}

void tc_kind_cleanup(void) {
    memset(g_registries, 0, sizeof(g_registries));
}
