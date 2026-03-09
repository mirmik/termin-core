// inspect_module.cpp - _inspect_native nanobind module
// Core InspectRegistry binding for termin-inspect.
// Domain-specific pointer extractors are registered by consumers (termin).

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <cstdint>
#include <cstdio>
#include <vector>
#include <functional>

#include "inspect/tc_inspect_python.hpp"
#include "inspect/tc_kind.h"
#include "inspect/tc_kind_python.hpp"
#include <tcbase/tc_log.hpp>

extern "C" {
#include "tc_value.h"
}

namespace nb = nanobind;

using tc::TypeBackend;
using tc::EnumChoice;
using tc::InspectFieldInfo;
using tc::InspectRegistry;

// ============================================================================
// Pluggable pointer extractor for domain types
// ============================================================================

using PtrExtractorFn = std::function<void*(nb::object)>;
static std::vector<PtrExtractorFn> g_ptr_extractors;

// Default: return PyObject* (works for pure Python objects)
static void* get_raw_pointer(nb::object obj) {
    // Try registered domain extractors first
    for (auto& extractor : g_ptr_extractors) {
        void* ptr = extractor(obj);
        if (ptr) return ptr;
    }
    // Fallback: return PyObject* for pure Python objects
    return static_cast<void*>(obj.ptr());
}

// Helper to extract short type name
static std::string get_short_type_name(const std::string& full_name) {
    size_t pos = full_name.rfind('.');
    if (pos != std::string::npos) {
        return full_name.substr(pos + 1);
    }
    return full_name;
}

// ============================================================================
// Builtin kind handlers
// ============================================================================

static void register_builtin_kind_handlers() {
    // enum kind handler - serializes enum.value (int), deserializes as-is
    tc::KindRegistry::instance().register_python(
        "enum",
        nb::cpp_function([](nb::object obj) -> nb::object {
            if (nb::hasattr(obj, "value")) {
                return obj.attr("value");
            }
            return obj;
        }),
        nb::cpp_function([](nb::object data) -> nb::object {
            return data;
        })
    );

    // layer_mask kind handler - stores 64-bit mask as hex string to avoid int64 overflow
    tc::KindRegistry::instance().register_python(
        "layer_mask",
        nb::cpp_function([](nb::object obj) -> nb::object {
            if (nb::isinstance<nb::str>(obj)) {
                return obj;
            }
            uint64_t mask = nb::cast<uint64_t>(obj);
            char buf[32];
            snprintf(buf, sizeof(buf), "0x%llx", static_cast<unsigned long long>(mask));
            return nb::str(buf);
        }),
        nb::cpp_function([](nb::object data) -> nb::object {
            if (nb::isinstance<nb::str>(data)) {
                std::string s = nb::cast<std::string>(data);
                uint64_t mask = 0;
                try {
                    size_t idx = 0;
                    mask = std::stoull(s, &idx, 0);
                } catch (...) {
                    mask = 0;
                }
                return nb::int_(mask);
            }
            return nb::int_(nb::cast<uint64_t>(data));
        })
    );
}

// Ensure list[X] kind has a Python handler
static bool ensure_list_handler_impl(const std::string& kind) {
    auto& py_reg = tc::KindRegistryPython::instance();

    if (py_reg.has(kind)) {
        return true;
    }

    char container[64], element[64];
    if (!tc_kind_parse(kind.c_str(), container, sizeof(container),
                      element, sizeof(element))) {
        return false;
    }

    if (std::string(container) != "list") {
        return false;
    }

    std::string elem_kind = element;
    if (!py_reg.has(elem_kind) && !tc::KindRegistryCpp::instance().has(elem_kind)) {
        return false;
    }

    nb::object serialize_fn = nb::cpp_function([elem_kind](nb::object obj) -> nb::object {
        nb::list result;
        if (obj.is_none()) return result;
        auto& py_reg = tc::KindRegistryPython::instance();
        for (auto item : obj) {
            nb::object nb_item = nb::borrow<nb::object>(item);
            if (py_reg.has(elem_kind)) {
                result.append(py_reg.serialize(elem_kind, nb_item));
            } else {
                result.append(nb_item);
            }
        }
        return result;
    });

    nb::object deserialize_fn = nb::cpp_function([elem_kind](nb::object data) -> nb::object {
        nb::list result;
        if (!nb::isinstance<nb::list>(data)) return result;
        auto& py_reg = tc::KindRegistryPython::instance();
        for (auto item : data) {
            nb::object nb_item = nb::borrow<nb::object>(item);
            if (py_reg.has(elem_kind)) {
                result.append(py_reg.deserialize(elem_kind, nb_item));
            } else {
                result.append(nb_item);
            }
        }
        return result;
    });

    serialize_fn.inc_ref();
    deserialize_fn.inc_ref();

    py_reg.register_kind(kind, serialize_fn, deserialize_fn);
    return true;
}

// ============================================================================
// tc_value helpers (inlined for the module)
// ============================================================================

static nb::object tc_value_to_py(const tc_value* v) {
    if (!v) return nb::none();
    switch (v->type) {
        case TC_VALUE_NIL: return nb::none();
        case TC_VALUE_INT: return nb::int_(v->data.i);
        case TC_VALUE_FLOAT: return nb::float_(v->data.f);
        case TC_VALUE_BOOL: return nb::bool_(v->data.b);
        case TC_VALUE_STRING: return v->data.s ? nb::str(v->data.s) : nb::none();
        case TC_VALUE_DICT: {
            nb::dict d;
            for (size_t i = 0; i < v->data.dict.count; i++) {
                const char* key = nullptr;
                tc_value* val = tc_value_dict_get_at(const_cast<tc_value*>(v), i, &key);
                if (key && val) {
                    d[key] = tc_value_to_py(val);
                }
            }
            return d;
        }
        case TC_VALUE_LIST: {
            nb::list l;
            for (size_t i = 0; i < v->data.list.count; i++) {
                l.append(tc_value_to_py(&v->data.list.items[i]));
            }
            return l;
        }
        default: return nb::none();
    }
}

// ============================================================================
// Module
// ============================================================================

NB_MODULE(_inspect_native, m) {
    m.doc() = "Inspect native module (InspectRegistry, Kind system)";

    // Initialize Python language vtable
    tc::init_python_lang_vtable();

    // Register builtin kind handlers
    register_builtin_kind_handlers();

    // Set lazy list handler
    tc::set_ensure_list_handler(ensure_list_handler_impl);

    // Diagnostics
    m.def("inspect_registry_address", []() -> uintptr_t {
        return reinterpret_cast<uintptr_t>(&InspectRegistry::instance());
    });
    m.def("kind_registry_cpp_address", []() -> uintptr_t {
        return reinterpret_cast<uintptr_t>(&tc::KindRegistryCpp::instance());
    });

    // Register pointer extractor (for domain types)
    m.def("register_ptr_extractor", [](nb::object fn) {
        g_ptr_extractors.push_back([fn](nb::object obj) -> void* {
            nb::object result = fn(obj);
            if (result.is_none()) return nullptr;
            return reinterpret_cast<void*>(nb::cast<uintptr_t>(result));
        });
    }, nb::arg("fn"),
       "Register a function that extracts raw pointer from domain objects. "
       "Returns uintptr_t or None.");

    // TypeBackend enum
    nb::enum_<TypeBackend>(m, "TypeBackend")
        .value("Cpp", TypeBackend::Cpp)
        .value("Python", TypeBackend::Python)
        .value("Rust", TypeBackend::Rust);

    // EnumChoice
    nb::class_<EnumChoice>(m, "EnumChoice")
        .def_ro("value", &EnumChoice::value)
        .def_ro("label", &EnumChoice::label);

    // InspectFieldInfo
    nb::class_<InspectFieldInfo>(m, "InspectFieldInfo")
        .def_ro("type_name", &InspectFieldInfo::type_name)
        .def_ro("path", &InspectFieldInfo::path)
        .def_ro("label", &InspectFieldInfo::label)
        .def_ro("kind", &InspectFieldInfo::kind)
        .def_ro("min", &InspectFieldInfo::min)
        .def_ro("max", &InspectFieldInfo::max)
        .def_ro("step", &InspectFieldInfo::step)
        .def_ro("is_serializable", &InspectFieldInfo::is_serializable)
        .def_ro("is_inspectable", &InspectFieldInfo::is_inspectable)
        .def_ro("choices", &InspectFieldInfo::choices)
        .def("invoke_action", [](InspectFieldInfo& self, nb::object obj) {
            if (!self.action) return;
            void* ptr = get_raw_pointer(std::move(obj));
            if (!ptr) return;
            tc::InspectContext inspect_context;
            self.action(ptr, inspect_context);
        }, nb::arg("obj"))
        .def_prop_ro("action", [](InspectFieldInfo& self) -> nb::object {
            if (!self.action) return nb::none();
            auto action_fn = self.action;
            return nb::cpp_function([action_fn](nb::object obj) {
                void* ptr = get_raw_pointer(std::move(obj));
                if (!ptr) return;
                tc::InspectContext inspect_context;
                action_fn(ptr, inspect_context);
            });
        });

    // InspectRegistry singleton
    nb::class_<InspectRegistry>(m, "InspectRegistry")
        .def_static("instance", &InspectRegistry::instance,
                    nb::rv_policy::reference)
        .def("fields", &InspectRegistry::fields,
             nb::arg("type_name"),
             nb::rv_policy::reference,
             "Get type's own fields only")
        .def("all_fields", &InspectRegistry::all_fields,
             nb::arg("type_name"),
             "Get all fields including inherited fields")
        .def("types", &InspectRegistry::types,
             "Get all registered type names")
        .def("register_python_fields", [](InspectRegistry& self, const std::string& type_name, nb::dict fields_dict) {
            tc::InspectRegistry_register_python_fields(self, type_name, std::move(fields_dict));
        }, nb::arg("type_name"), nb::arg("fields_dict"),
           "Register fields from Python inspect_fields dict")
        .def("get_type_backend", &InspectRegistry::get_type_backend,
             nb::arg("type_name"),
             "Get the backend (Cpp/Python/Rust) for a type")
        .def("has_type", &InspectRegistry::has_type,
             nb::arg("type_name"),
             "Check if type is registered")
        .def("set_type_parent", &InspectRegistry::set_type_parent,
             nb::arg("type_name"), nb::arg("parent_name"),
             "Set parent type for field inheritance")
        .def("get_type_parent", &InspectRegistry::get_type_parent,
             nb::arg("type_name"),
             "Get parent type name")

        .def("get", [](InspectRegistry& self, nb::object obj, const std::string& field_path) {
            std::string full_type_name = nb::cast<std::string>(nb::str(nb::type_name(obj.type())));
            std::string type_name = get_short_type_name(full_type_name);
            void* ptr = get_raw_pointer(obj);
            return tc::InspectRegistry_get(self, ptr, type_name, field_path);
        }, nb::arg("obj"), nb::arg("field"),
           "Get field value from object")

        .def("set", [](InspectRegistry& self, nb::object obj, const std::string& field_path, nb::object value) {
            std::string full_type_name = nb::cast<std::string>(nb::str(nb::type_name(obj.type())));
            std::string type_name = get_short_type_name(full_type_name);
            void* ptr = get_raw_pointer(obj);
            tc::InspectRegistry_set(self, ptr, type_name, field_path, std::move(value));
        }, nb::arg("obj"), nb::arg("field"), nb::arg("value"),
           "Set field value on object")

        .def("serialize_all", [](InspectRegistry& self, nb::object obj) {
            std::string full_type_name = nb::cast<std::string>(nb::str(nb::type_name(obj.type())));
            std::string type_name = get_short_type_name(full_type_name);
            void* ptr = get_raw_pointer(obj);
            tc_value v = self.serialize_all(ptr, type_name);
            nb::object result = tc_value_to_py(&v);
            tc_value_free(&v);
            return result;
        }, nb::arg("obj"),
           "Serialize all fields of object to dict")

        .def("deserialize_all", [](InspectRegistry& self, nb::object obj, nb::object data) {
            std::string full_type_name = nb::cast<std::string>(nb::str(nb::type_name(obj.type())));
            std::string type_name = get_short_type_name(full_type_name);
            void* ptr = get_raw_pointer(obj);
            nb::dict py_data = nb::cast<nb::dict>(data);
            tc::InspectRegistry_deserialize_component_fields_over_python(self, ptr, obj, type_name, py_data);
        }, nb::arg("obj"), nb::arg("data"),
           "Deserialize all fields from dict to object")

        .def("add_button", [](InspectRegistry& self, const std::string& type_name,
                              const std::string& path, const std::string& label, nb::object action) {
            tc::InspectRegistry_add_button(self, type_name, path, label, std::move(action));
        }, nb::arg("type_name"), nb::arg("path"), nb::arg("label"), nb::arg("action"),
           "Add a button field to a type");

    // Register atexit handler to clear Python objects before interpreter shutdown.
    // Static singletons (KindRegistryPython, g_ptr_extractors) have destructors
    // that run after Python finalization, causing segfault on nb::object release.
    nb::object atexit_mod = nb::module_::import_("atexit");
    nb::object cleanup_fn = nb::cpp_function([]() {
        g_ptr_extractors.clear();
        tc::KindRegistry::instance().clear_python();
    });
    atexit_mod.attr("register")(cleanup_fn);
}
