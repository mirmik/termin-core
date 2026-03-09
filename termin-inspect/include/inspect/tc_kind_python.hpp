// tc_kind_python.hpp - Python bindings for kind serialization
// Extends KindRegistryCpp with Python-specific handlers via nanobind.
#pragma once

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <string>
#include <unordered_map>

#include "inspect/tc_kind_cpp.hpp"

// DLL export/import macros for termin-inspect Python bridge
#ifdef _WIN32
    #ifdef TERMIN_INSPECT_PYTHON_EXPORTS
        #define TC_KIND_PYTHON_API __declspec(dllexport)
    #else
        #define TC_KIND_PYTHON_API __declspec(dllimport)
    #endif
#else
    #define TC_KIND_PYTHON_API __attribute__((visibility("default")))
#endif

namespace nb = nanobind;

namespace tc {

// Python kind handler - uses nb::object for Python callables
#ifdef _WIN32
struct KindPython {
#else
struct __attribute__((visibility("hidden"))) KindPython {
#endif
    std::string name;
    nb::object serialize;    // callable(obj) -> dict
    nb::object deserialize;  // callable(dict) -> obj

    bool is_valid() const {
        return serialize.ptr() != nullptr && deserialize.ptr() != nullptr;
    }
};

// Python Kind Registry - manages Python serialization handlers
// Works alongside KindRegistryCpp.
class TC_KIND_PYTHON_API KindRegistryPython {
    std::unordered_map<std::string, KindPython> _kinds;
    std::vector<std::pair<nb::object, std::string>> _type_to_kind;

public:
    // Singleton - defined in tc_kind_python_instance.cpp
    static KindRegistryPython& instance();

    // Register Python handler
    void register_kind(const std::string& name, nb::object serialize, nb::object deserialize);

    // Register Python type → kind name mapping
    void register_type(nb::handle type, const std::string& kind_name);

    // Find kind name for a Python object by its type (returns "" if not found)
    std::string kind_for_object(nb::handle obj) const;

    // Get handler (returns nullptr if not found)
    KindPython* get(const std::string& name);
    const KindPython* get(const std::string& name) const;

    bool has(const std::string& name) const;

    // Get all registered kind names
    std::vector<std::string> kinds() const;

    // Serialize value using Python handler
    nb::object serialize(const std::string& kind_name, nb::object obj) const;

    // Deserialize value using Python handler
    nb::object deserialize(const std::string& kind_name, nb::object data) const;

    // Clear all Python references (call before Python finalization)
    void clear();
};

// Unified Kind Registry - facade for C++ and Python registries
// This is what Python code interacts with.
class TC_KIND_PYTHON_API KindRegistry {
public:
    // Singleton - defined in tc_kind_python_instance.cpp
    static KindRegistry& instance();

    // Check if kind has C++ handler
    bool has_cpp(const std::string& name) const;

    // Check if kind has Python handler
    bool has_python(const std::string& name) const;

    // Get all kinds (combined from both registries)
    std::vector<std::string> kinds() const;

    // Register C++ handler (delegates to KindRegistryCpp)
    void register_cpp(
        const std::string& name,
        std::function<tc_value(const std::any&)> serialize,
        std::function<std::any(const tc_value*, void*)> deserialize
    );

    // Register Python handler (delegates to KindRegistryPython)
    void register_python(const std::string& name, nb::object serialize, nb::object deserialize);

    // Register Python type → kind name mapping
    void register_type(nb::handle type, const std::string& kind_name);

    // Find kind name for a Python object by its type
    std::string kind_for_object(nb::handle obj) const;

    // Serialize using C++ handler (caller owns returned tc_value)
    tc_value serialize_cpp(const std::string& kind_name, const std::any& value) const;

    // Deserialize using C++ handler
    std::any deserialize_cpp(const std::string& kind_name, const tc_value* data, void* context = nullptr) const;

    // Serialize using Python handler
    nb::object serialize_python(const std::string& kind_name, nb::object obj) const;

    // Deserialize using Python handler
    nb::object deserialize_python(const std::string& kind_name, nb::object data) const;

    // Clear Python references
    void clear_python();

    // Access to underlying registries
    KindRegistryCpp& cpp();
    const KindRegistryCpp& cpp() const;

    KindRegistryPython& python();
    const KindRegistryPython& python() const;
};

// Bind KindRegistry to Python
inline void bind_kind_registry(nb::module_& m) {
    nb::class_<KindRegistry>(m, "KindRegistry")
        .def_static("instance", &KindRegistry::instance, nb::rv_policy::reference)
        .def("kinds", &KindRegistry::kinds)
        .def("has_cpp", &KindRegistry::has_cpp, nb::arg("name"))
        .def("has_python", &KindRegistry::has_python, nb::arg("name"))
        .def("register_python", &KindRegistry::register_python,
             nb::arg("name"), nb::arg("serialize"), nb::arg("deserialize"))
        .def("register_type", [](KindRegistry& self, nb::handle type, const std::string& kind_name) {
            self.register_type(type, kind_name);
        }, nb::arg("type"), nb::arg("kind_name"))
        .def("kind_for_object", &KindRegistry::kind_for_object,
             nb::arg("obj"))
        .def("serialize", &KindRegistry::serialize_python,
             nb::arg("kind"), nb::arg("obj"))
        .def("deserialize", &KindRegistry::deserialize_python,
             nb::arg("kind"), nb::arg("data"));
}

// Initialize Python language vtable in C dispatcher
// Called from inspect_bindings.cpp at module init
TC_KIND_PYTHON_API void init_python_lang_vtable();

// Callback type for lazy list handler creation
using EnsureListHandlerFn = bool(*)(const std::string&);

// Global callback pointer - set by inspect_bindings.cpp at module init
TC_KIND_PYTHON_API extern EnsureListHandlerFn g_ensure_list_handler;

// Ensure list[X] kind has a Python handler (lazy creation)
// Calls the callback if set, otherwise returns false
inline bool ensure_list_handler(const std::string& kind) {
    if (g_ensure_list_handler) {
        return g_ensure_list_handler(kind);
    }
    return false;
}

// Set the list handler callback (called from inspect_bindings.cpp)
inline void set_ensure_list_handler(EnsureListHandlerFn fn) {
    g_ensure_list_handler = fn;
}

} // namespace tc
