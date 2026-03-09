// tc_inspect_python.hpp - Python/nanobind extensions for tc_inspect
// For C++-only code, use tc_inspect_cpp.hpp instead.
#pragma once

#include "tc_inspect_cpp.hpp"
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "inspect/tc_kind_python.hpp"

// DLL export/import macros for termin-inspect Python bridge
#ifdef _WIN32
    #ifdef TERMIN_INSPECT_PYTHON_EXPORTS
        #define TC_INSPECT_PYTHON_API __declspec(dllexport)
    #else
        #define TC_INSPECT_PYTHON_API __declspec(dllimport)
    #endif
#else
    #define TC_INSPECT_PYTHON_API __attribute__((visibility("default")))
#endif

namespace nb = nanobind;

namespace tc {

// ============================================================================
// nb::object <-> tc_value conversion
// ============================================================================

inline tc_value nb_to_tc_value(nb::object obj);
inline nb::object tc_value_to_nb(const tc_value* v);

inline tc_value nb_to_tc_value(nb::object obj) {
    if (obj.is_none()) {
        return tc_value_nil();
    }

    if (nb::isinstance<nb::bool_>(obj)) {
        return tc_value_bool(nb::cast<bool>(obj));
    }

    if (nb::isinstance<nb::int_>(obj)) {
        return tc_value_int(nb::cast<int64_t>(obj));
    }

    if (nb::isinstance<nb::float_>(obj)) {
        return tc_value_double(nb::cast<double>(obj));
    }

    if (nb::isinstance<nb::str>(obj)) {
        return tc_value_string(nb::cast<std::string>(obj).c_str());
    }

    if (nb::isinstance<nb::list>(obj) || nb::isinstance<nb::tuple>(obj)) {
        tc_value list = tc_value_list_new();
        for (auto item : obj) {
            tc_value_list_push(&list, nb_to_tc_value(nb::borrow<nb::object>(item)));
        }
        return list;
    }

    if (nb::isinstance<nb::dict>(obj)) {
        tc_value dict = tc_value_dict_new();
        for (auto item : nb::cast<nb::dict>(obj)) {
            std::string key = nb::cast<std::string>(nb::str(item.first));
            tc_value_dict_set(&dict, key.c_str(),
                nb_to_tc_value(nb::borrow<nb::object>(item.second)));
        }
        return dict;
    }

    // Try numpy array / vec3-like
    if (nb::hasattr(obj, "__len__") && nb::len(obj) == 3) {
        try {
            nb::list lst = nb::cast<nb::list>(obj);
            tc_vec3 v = {
                nb::cast<double>(lst[0]),
                nb::cast<double>(lst[1]),
                nb::cast<double>(lst[2])
            };
            return tc_value_vec3(v);
        } catch (...) {}
    }

    // Fallback: try tolist() for numpy
    if (nb::hasattr(obj, "tolist")) {
        return nb_to_tc_value(obj.attr("tolist")());
    }

    return tc_value_nil();
}

inline nb::object tc_value_to_nb(const tc_value* v) {
    if (!v) return nb::none();

    switch (v->type) {
    case TC_VALUE_NIL:
        return nb::none();

    case TC_VALUE_BOOL:
        return nb::bool_(v->data.b);

    case TC_VALUE_INT:
        return nb::int_(v->data.i);

    case TC_VALUE_FLOAT:
        return nb::float_(v->data.f);

    case TC_VALUE_DOUBLE:
        return nb::float_(v->data.d);

    case TC_VALUE_STRING:
        if (v->data.s) return nb::str(v->data.s);
        return nb::none();

    case TC_VALUE_VEC3: {
        nb::list lst;
        lst.append(v->data.v3.x);
        lst.append(v->data.v3.y);
        lst.append(v->data.v3.z);
        return lst;
    }

    case TC_VALUE_QUAT: {
        nb::list lst;
        lst.append(v->data.q.x);
        lst.append(v->data.q.y);
        lst.append(v->data.q.z);
        lst.append(v->data.q.w);
        return lst;
    }

    case TC_VALUE_LIST: {
        nb::list lst;
        for (size_t i = 0; i < v->data.list.count; i++) {
            lst.append(tc_value_to_nb(&v->data.list.items[i]));
        }
        return lst;
    }

    case TC_VALUE_DICT: {
        nb::dict d;
        for (size_t i = 0; i < v->data.dict.count; i++) {
            d[nb::str(v->data.dict.entries[i].key)] =
                tc_value_to_nb(v->data.dict.entries[i].value);
        }
        return d;
    }

    default:
        return nb::none();
    }
}

// ============================================================================
// InspectRegistry Python extension methods
// These are added to InspectRegistry when nanobind is available
// ============================================================================

// Extend InspectRegistry with Python-specific methods
// Implemented in tc_inspect_python.cpp
class TC_INSPECT_PYTHON_API InspectRegistryPythonExt {
public:
    // Add a button field with Python action
    static void add_button(InspectRegistry& reg, const std::string& type_name,
                           const std::string& path, const std::string& label, nb::object action);

    // Register Python component fields
    static void register_python_fields(InspectRegistry& reg, const std::string& type_name,
                                        nb::dict fields_dict);

    // Field access with nb::object (uses tc_value internally)
    static nb::object get(InspectRegistry& reg, void* obj, const std::string& type_name,
                          const std::string& field_path);
    static void set(InspectRegistry& reg, void* obj, const std::string& type_name,
                    const std::string& field_path, nb::object value, void* context = nullptr);

    // Deserialization from nb::dict
    static void deserialize_all_py(InspectRegistry& reg, void* obj, const std::string& type_name,
                                   const nb::dict& data, void* context = nullptr);

    // Legacy compatibility
    static void deserialize_component_fields_over_python(
        InspectRegistry& reg, void* ptr, nb::object obj, const std::string& type_name,
        const nb::dict& data, void* context = nullptr);
};

// Convenience methods added to InspectRegistry when nanobind is available
// These call InspectRegistryPythonExt static methods
inline void InspectRegistry_add_button(InspectRegistry& reg, const std::string& type_name,
                                       const std::string& path, const std::string& label,
                                       nb::object action) {
    InspectRegistryPythonExt::add_button(reg, type_name, path, label, std::move(action));
}

inline void InspectRegistry_register_python_fields(InspectRegistry& reg, const std::string& type_name,
                                                   nb::dict fields_dict) {
    InspectRegistryPythonExt::register_python_fields(reg, type_name, std::move(fields_dict));
}

inline nb::object InspectRegistry_get(InspectRegistry& reg, void* obj,
                                      const std::string& type_name, const std::string& field_path) {
    return InspectRegistryPythonExt::get(reg, obj, type_name, field_path);
}

inline void InspectRegistry_set(InspectRegistry& reg, void* obj, const std::string& type_name,
                                const std::string& field_path, nb::object value, void* context = nullptr) {
    InspectRegistryPythonExt::set(reg, obj, type_name, field_path, std::move(value), context);
}

inline void InspectRegistry_deserialize_all_py(InspectRegistry& reg, void* obj,
                                               const std::string& type_name,
                                               const nb::dict& data, void* context = nullptr) {
    InspectRegistryPythonExt::deserialize_all_py(reg, obj, type_name, data, context);
}

inline void InspectRegistry_deserialize_component_fields_over_python(
    InspectRegistry& reg, void* ptr, nb::object obj, const std::string& type_name,
    const nb::dict& data, void* context = nullptr) {
    InspectRegistryPythonExt::deserialize_component_fields_over_python(reg, ptr, obj, type_name, data, context);
}

} // namespace tc
