// tc_kind_cpp.cpp - KindRegistryCpp singleton and C++ language vtable registration
// Compiled into entity_lib to ensure single instance across all modules

#include "inspect/tc_kind_cpp.hpp"
#include <cstring>

extern "C" {
#include "inspect/tc_kind.h"
}

namespace tc {

// ============================================================================
// C++ language vtable callbacks for C dispatcher
// ============================================================================

static bool cpp_has(const char* kind_name, void* ctx) {
    (void)ctx;
    return KindRegistryCpp::instance().has(kind_name);
}

static tc_value cpp_serialize(const char* kind_name, const tc_value* input, void* ctx) {
    (void)ctx;
    // For C++ kinds, actual serialization is done via KindRegistryCpp::serialize()
    // which works with std::any. This callback is pass-through since the value
    // is already serialized by the time it reaches the C API.
    if (!input) return tc_value_nil();
    return tc_value_copy(input);
}

static tc_value cpp_deserialize(const char* kind_name, const tc_value* input, void* context, void* ctx) {
    (void)ctx;
    (void)context;
    if (!input || !kind_name) return tc_value_nil();

    // vec3: list [x, y, z] → TC_VALUE_VEC3
    if (strcmp(kind_name, "vec3") == 0) {
        if (input->type == TC_VALUE_VEC3) return tc_value_copy(input);
        if (input->type == TC_VALUE_LIST && input->data.list.count >= 3) {
            tc_vec3 v;
            v.x = tc_value_to_double(&input->data.list.items[0]);
            v.y = tc_value_to_double(&input->data.list.items[1]);
            v.z = tc_value_to_double(&input->data.list.items[2]);
            return tc_value_vec3(v);
        }
        return tc_value_nil();
    }

    // quat: list [w, x, y, z] → TC_VALUE_QUAT
    if (strcmp(kind_name, "quat") == 0) {
        if (input->type == TC_VALUE_QUAT) return tc_value_copy(input);
        if (input->type == TC_VALUE_LIST && input->data.list.count >= 4) {
            tc_quat q;
            q.w = tc_value_to_double(&input->data.list.items[0]);
            q.x = tc_value_to_double(&input->data.list.items[1]);
            q.y = tc_value_to_double(&input->data.list.items[2]);
            q.z = tc_value_to_double(&input->data.list.items[3]);
            return tc_value_quat(q);
        }
        return tc_value_nil();
    }

    // Default: pass-through
    return tc_value_copy(input);
}

static size_t cpp_list(const char** out_names, size_t max_count, void* ctx) {
    (void)ctx;
    auto kinds = KindRegistryCpp::instance().kinds();
    size_t count = std::min(kinds.size(), max_count);
    if (out_names) {
        // Note: returning pointers to temporary strings is unsafe for this API
        // For now, we just return the count. Caller should use KindRegistryCpp::kinds() directly.
    }
    return kinds.size();
}

static bool g_cpp_vtable_initialized = false;

static void init_cpp_lang_vtable() {
    if (g_cpp_vtable_initialized) return;
    g_cpp_vtable_initialized = true;

    static tc_kind_lang_registry cpp_registry = {
        cpp_has,
        cpp_serialize,
        cpp_deserialize,
        cpp_list,
        nullptr
    };

    tc_kind_set_lang_registry(TC_KIND_LANG_CPP, &cpp_registry);
}

// Singleton
// ============================================================================

KindRegistryCpp& KindRegistryCpp::instance() {
    static KindRegistryCpp inst;

    // Ensure vtable is registered on first access
    init_cpp_lang_vtable();

    // Register builtin kinds on first access
    static bool builtins_registered = false;
    if (!builtins_registered) {
        builtins_registered = true;
        register_builtin_cpp_kinds();
    }

    return inst;
}

// ============================================================================
// KindRegistryCpp methods (exported from DLL)
// ============================================================================

void KindRegistryCpp::register_kind(
    const std::string& name,
    std::function<tc_value(const std::any&)> serialize,
    std::function<std::any(const tc_value*, void*)> deserialize
) {
    KindCpp kind;
    kind.name = name;
    kind.serialize = std::move(serialize);
    kind.deserialize = std::move(deserialize);
    _kinds[name] = std::move(kind);
}

KindCpp* KindRegistryCpp::get(const std::string& name) {
    auto it = _kinds.find(name);
    return it != _kinds.end() ? &it->second : nullptr;
}

const KindCpp* KindRegistryCpp::get(const std::string& name) const {
    auto it = _kinds.find(name);
    return it != _kinds.end() ? &it->second : nullptr;
}

bool KindRegistryCpp::has(const std::string& name) const {
    return _kinds.find(name) != _kinds.end();
}

std::vector<std::string> KindRegistryCpp::kinds() const {
    std::vector<std::string> result;
    result.reserve(_kinds.size());
    for (const auto& [name, _] : _kinds) {
        result.push_back(name);
    }
    return result;
}

tc_value KindRegistryCpp::serialize(const std::string& kind_name, const std::any& value) const {
    auto* kind = get(kind_name);
    if (kind && kind->serialize) {
        return kind->serialize(value);
    }
    return tc_value_nil();
}

std::any KindRegistryCpp::deserialize(const std::string& kind_name, const tc_value* data, void* context) const {
    auto* kind = get(kind_name);
    if (!kind) {
        tc_log(TC_LOG_WARN, "[Inspect] Kind '%s' not registered in KindRegistryCpp", kind_name.c_str());
        return std::any{};
    }
    if (!kind->deserialize) {
        tc_log(TC_LOG_WARN, "[Inspect] Kind '%s' has no deserialize handler", kind_name.c_str());
        return std::any{};
    }
    return kind->deserialize(data, context);
}

} // namespace tc
