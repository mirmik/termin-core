// tc_kind_python_instance.cpp - KindRegistryPython and KindRegistry singleton implementation
// Compiled into entity_lib to ensure single instance across all modules

#include "inspect/tc_kind_python.hpp"

extern "C" {
#include "inspect/tc_kind.h"
}

namespace tc {

// Global callback for lazy list handler creation
// Set by inspect_bindings.cpp at Python module init
EnsureListHandlerFn g_ensure_list_handler = nullptr;

// ============================================================================
// Python language vtable callbacks for C dispatcher
// ============================================================================

static bool python_has(const char* kind_name, void* ctx) {
    (void)ctx;
    return KindRegistryPython::instance().has(kind_name);
}

static tc_value python_serialize(const char* kind_name, const tc_value* input, void* ctx) {
    (void)ctx;
    (void)kind_name;
    // For Python kinds, actual serialization is done via KindRegistryPython::serialize()
    // which works with nb::object. This callback is pass-through.
    if (!input) return tc_value_nil();
    return tc_value_copy(input);
}

static tc_value python_deserialize(const char* kind_name, const tc_value* input, void* context, void* ctx) {
    (void)ctx;
    (void)kind_name;
    (void)context;
    // For Python kinds, actual deserialization is done via KindRegistryPython::deserialize()
    // which works with nb::object. This callback is pass-through.
    if (!input) return tc_value_nil();
    return tc_value_copy(input);
}

static size_t python_list(const char** out_names, size_t max_count, void* ctx) {
    (void)ctx;
    (void)out_names;
    (void)max_count;
    auto kinds = KindRegistryPython::instance().kinds();
    return kinds.size();
}

static bool g_python_vtable_initialized = false;

void init_python_lang_vtable() {
    if (g_python_vtable_initialized) return;
    g_python_vtable_initialized = true;

    static tc_kind_lang_registry python_registry = {
        python_has,
        python_serialize,
        python_deserialize,
        python_list,
        nullptr
    };

    tc_kind_set_lang_registry(TC_KIND_LANG_PYTHON, &python_registry);
}

// ============================================================================
// KindRegistryPython methods
// ============================================================================

KindRegistryPython& KindRegistryPython::instance() {
    static KindRegistryPython inst;
    return inst;
}

void KindRegistryPython::register_kind(const std::string& name, nb::object serialize, nb::object deserialize) {
    KindPython kind;
    kind.name = name;
    kind.serialize = std::move(serialize);
    kind.deserialize = std::move(deserialize);
    _kinds[name] = std::move(kind);
}

KindPython* KindRegistryPython::get(const std::string& name) {
    auto it = _kinds.find(name);
    return it != _kinds.end() ? &it->second : nullptr;
}

const KindPython* KindRegistryPython::get(const std::string& name) const {
    auto it = _kinds.find(name);
    return it != _kinds.end() ? &it->second : nullptr;
}

bool KindRegistryPython::has(const std::string& name) const {
    return _kinds.find(name) != _kinds.end();
}

std::vector<std::string> KindRegistryPython::kinds() const {
    std::vector<std::string> result;
    result.reserve(_kinds.size());
    for (const auto& [name, _] : _kinds) {
        result.push_back(name);
    }
    return result;
}

nb::object KindRegistryPython::serialize(const std::string& kind_name, nb::object obj) const {
    auto* kind = get(kind_name);
    if (kind && kind->serialize.ptr()) {
        return kind->serialize(obj);
    }
    return nb::none();
}

nb::object KindRegistryPython::deserialize(const std::string& kind_name, nb::object data) const {
    auto* kind = get(kind_name);
    if (kind && kind->deserialize.ptr()) {
        return kind->deserialize(data);
    }
    return nb::none();
}

void KindRegistryPython::register_type(nb::handle type, const std::string& kind_name) {
    _type_to_kind.emplace_back(nb::borrow(type), kind_name);
}

std::string KindRegistryPython::kind_for_object(nb::handle obj) const {
    PyObject* obj_type = (PyObject*)Py_TYPE(obj.ptr());
    for (const auto& [type, kind_name] : _type_to_kind) {
        if (type.ptr() == obj_type) return kind_name;
    }
    return "";
}

void KindRegistryPython::clear() {
    for (auto& [name, kind] : _kinds) {
        kind.serialize = nb::object();
        kind.deserialize = nb::object();
    }
    _kinds.clear();
    _type_to_kind.clear();
}

// ============================================================================
// KindRegistry methods
// ============================================================================

KindRegistry& KindRegistry::instance() {
    static KindRegistry inst;
    return inst;
}

bool KindRegistry::has_cpp(const std::string& name) const {
    return KindRegistryCpp::instance().has(name);
}

bool KindRegistry::has_python(const std::string& name) const {
    return KindRegistryPython::instance().has(name);
}

std::vector<std::string> KindRegistry::kinds() const {
    std::vector<std::string> result;

    // Add C++ kinds
    for (const auto& name : KindRegistryCpp::instance().kinds()) {
        result.push_back(name);
    }

    // Add Python kinds (if not already present)
    for (const auto& name : KindRegistryPython::instance().kinds()) {
        bool found = false;
        for (const auto& existing : result) {
            if (existing == name) {
                found = true;
                break;
            }
        }
        if (!found) {
            result.push_back(name);
        }
    }

    return result;
}

void KindRegistry::register_cpp(
    const std::string& name,
    std::function<tc_value(const std::any&)> serialize,
    std::function<std::any(const tc_value*, void*)> deserialize
) {
    KindRegistryCpp::instance().register_kind(name, serialize, deserialize);
}

void KindRegistry::register_python(const std::string& name, nb::object serialize, nb::object deserialize) {
    KindRegistryPython::instance().register_kind(name, serialize, deserialize);
}

tc_value KindRegistry::serialize_cpp(const std::string& kind_name, const std::any& value) const {
    return KindRegistryCpp::instance().serialize(kind_name, value);
}

std::any KindRegistry::deserialize_cpp(const std::string& kind_name, const tc_value* data, void* context) const {
    return KindRegistryCpp::instance().deserialize(kind_name, data, context);
}

nb::object KindRegistry::serialize_python(const std::string& kind_name, nb::object obj) const {
    return KindRegistryPython::instance().serialize(kind_name, obj);
}

nb::object KindRegistry::deserialize_python(const std::string& kind_name, nb::object data) const {
    return KindRegistryPython::instance().deserialize(kind_name, data);
}

void KindRegistry::register_type(nb::handle type, const std::string& kind_name) {
    KindRegistryPython::instance().register_type(type, kind_name);
}

std::string KindRegistry::kind_for_object(nb::handle obj) const {
    return KindRegistryPython::instance().kind_for_object(obj);
}

void KindRegistry::clear_python() {
    KindRegistryPython::instance().clear();
}

KindRegistryCpp& KindRegistry::cpp() { return KindRegistryCpp::instance(); }
const KindRegistryCpp& KindRegistry::cpp() const { return KindRegistryCpp::instance(); }

KindRegistryPython& KindRegistry::python() { return KindRegistryPython::instance(); }
const KindRegistryPython& KindRegistry::python() const { return KindRegistryPython::instance(); }

} // namespace tc
