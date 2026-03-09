// tc_inspect_python.cpp - InspectRegistryPythonExt implementation
// Python-specific extensions for tc_inspect

#include "inspect/tc_inspect_python.hpp"
#include "inspect/tc_kind_python.hpp"
#include <tcbase/tc_log.hpp>

#include <iostream>

namespace tc {

void InspectRegistryPythonExt::add_button(InspectRegistry& reg, const std::string& type_name,
                                          const std::string& path, const std::string& label,
                                          nb::object action) {
    InspectFieldInfo info;
    info.type_name = type_name;
    info.path = path;
    info.label = label;
    info.kind = "button";
    info.is_serializable = false;
    info.is_inspectable = true;

    // Wrap Python callable into unified action: PyObject* → callable
    nb::object py_action = std::move(action);
    py_action.inc_ref();  // prevent GC
    info.action = [py_action](void* obj, const InspectContext&) {
        if (!obj) return;
        nb::object py_obj = nb::borrow<nb::object>(
            nb::handle(static_cast<PyObject*>(obj)));
        py_action(py_obj);
    };

    reg._fields[type_name].push_back(std::move(info));
}

void InspectRegistryPythonExt::register_python_fields(InspectRegistry& reg, const std::string& type_name,
                                                       nb::dict fields_dict) {
    reg._fields.erase(type_name);

    for (auto item : fields_dict) {
        std::string field_name = nb::cast<std::string>(item.first);
        nb::object field_obj = nb::borrow<nb::object>(item.second);

        InspectFieldInfo info;
        info.type_name = type_name;

        // Extract attributes
        info.path = field_name;
        if (nb::hasattr(field_obj, "path") && !field_obj.attr("path").is_none()) {
            info.path = nb::cast<std::string>(field_obj.attr("path"));
        }

        info.label = field_name;
        if (nb::hasattr(field_obj, "label") && !field_obj.attr("label").is_none()) {
            info.label = nb::cast<std::string>(field_obj.attr("label"));
        }

        info.kind = "float";
        if (nb::hasattr(field_obj, "kind")) {
            info.kind = nb::cast<std::string>(field_obj.attr("kind"));
        }

        if (nb::hasattr(field_obj, "min") && !field_obj.attr("min").is_none()) {
            info.min = nb::cast<double>(field_obj.attr("min"));
        }
        if (nb::hasattr(field_obj, "max") && !field_obj.attr("max").is_none()) {
            info.max = nb::cast<double>(field_obj.attr("max"));
        }
        if (nb::hasattr(field_obj, "step") && !field_obj.attr("step").is_none()) {
            info.step = nb::cast<double>(field_obj.attr("step"));
        }

        // is_serializable (default true, can be set via is_serializable=False or legacy non_serializable=True)
        if (nb::hasattr(field_obj, "is_serializable")) {
            info.is_serializable = nb::cast<bool>(field_obj.attr("is_serializable"));
        } else if (nb::hasattr(field_obj, "non_serializable")) {
            info.is_serializable = !nb::cast<bool>(field_obj.attr("non_serializable"));
        }

        // is_inspectable (default true)
        if (nb::hasattr(field_obj, "is_inspectable")) {
            info.is_inspectable = nb::cast<bool>(field_obj.attr("is_inspectable"));
        }

        // Choices for enum
        if (nb::hasattr(field_obj, "choices") && !field_obj.attr("choices").is_none()) {
            for (auto c : field_obj.attr("choices")) {
                nb::tuple t = nb::cast<nb::tuple>(c);
                if (t.size() >= 2) {
                    EnumChoice choice;
                    // Convert value to string (handles ints, enums, strings)
                    nb::object val_obj = nb::borrow<nb::object>(t[0]);
                    if (nb::isinstance<nb::str>(val_obj)) {
                        choice.value = nb::cast<std::string>(val_obj);
                    } else if (nb::isinstance<nb::int_>(val_obj)) {
                        choice.value = std::to_string(nb::cast<int64_t>(val_obj));
                    } else {
                        // Fallback: use Python str()
                        choice.value = nb::cast<std::string>(nb::str(val_obj));
                    }
                    choice.label = nb::cast<std::string>(t[1]);
                    info.choices.push_back(choice);
                }
            }
        }

        // Action for button — wrap Python callable into unified action
        if (nb::hasattr(field_obj, "action") && !field_obj.attr("action").is_none()) {
            nb::object py_action = field_obj.attr("action");
            py_action.inc_ref();  // prevent GC
            info.action = [py_action](void* obj, const InspectContext&) {
                if (!obj) return;
                nb::object py_obj = nb::borrow<nb::object>(
                    nb::handle(static_cast<PyObject*>(obj)));
                py_action(py_obj);
            };
        }

        // Custom getter/setter from Python InspectField
        nb::object py_getter = nb::none();
        nb::object py_setter = nb::none();
        if (nb::hasattr(field_obj, "getter") && !field_obj.attr("getter").is_none()) {
            py_getter = field_obj.attr("getter");
        }
        if (nb::hasattr(field_obj, "setter") && !field_obj.attr("setter").is_none()) {
            py_setter = field_obj.attr("setter");
        }

        std::string path_copy = info.path;
        std::string kind_copy = info.kind;

        info.getter = [path_copy, kind_copy, py_getter](void* obj) -> tc_value {
            // obj is PyObject* for Python types
            nb::object py_obj = nb::borrow<nb::object>(
                nb::handle(static_cast<PyObject*>(obj)));

            nb::object result;
            if (!py_getter.is_none()) {
                result = py_getter(py_obj);
            } else {
                // Use getattr for path resolution
                result = py_obj;
                size_t start = 0, end;
                while ((end = path_copy.find('.', start)) != std::string::npos) {
                    result = nb::getattr(result, path_copy.substr(start, end - start).c_str());
                    start = end + 1;
                }
                result = nb::getattr(result, path_copy.substr(start).c_str());
            }

            // Serialize through kind handler if available
            ensure_list_handler(kind_copy);
            auto& py_reg = KindRegistryPython::instance();
            if (py_reg.has(kind_copy)) {
                result = py_reg.serialize(kind_copy, result);
            }
            return nb_to_tc_value(result);
        };

        info.setter = [path_copy, kind_copy, py_setter](void* obj, tc_value value, void*) {
            try {
                // obj is PyObject* for Python types
                nb::object py_obj = nb::borrow<nb::object>(
                    nb::handle(static_cast<PyObject*>(obj)));

                // Convert tc_value to Python object
                nb::object py_value = tc_value_to_nb(&value);

                // Deserialize through kind handler if available
                ensure_list_handler(kind_copy);
                auto& py_reg = KindRegistryPython::instance();
                if (py_reg.has(kind_copy)) {
                    py_value = py_reg.deserialize(kind_copy, py_value);
                }

                if (!py_setter.is_none()) {
                    py_setter(py_obj, py_value);
                    return;
                }

                // Use setattr for path resolution
                nb::object target = py_obj;
                std::vector<std::string> parts;
                size_t start = 0, end;
                while ((end = path_copy.find('.', start)) != std::string::npos) {
                    parts.push_back(path_copy.substr(start, end - start));
                    start = end + 1;
                }
                parts.push_back(path_copy.substr(start));

                for (size_t i = 0; i < parts.size() - 1; ++i) {
                    target = nb::getattr(target, parts[i].c_str());
                }
                nb::setattr(target, parts.back().c_str(), py_value);
            } catch (const std::exception& e) {
                std::cerr << "[Python setter error] path=" << path_copy
                          << " error=" << e.what() << std::endl;
            }
        };

        reg._fields[type_name].push_back(std::move(info));
    }

    reg._type_backends[type_name] = TypeBackend::Python;
}

nb::object InspectRegistryPythonExt::get(InspectRegistry& reg, void* obj,
                                         const std::string& type_name, const std::string& field_path) {
    const InspectFieldInfo* f = reg.find_field(type_name, field_path);
    if (!f) {
        throw nb::attribute_error(("Field not found: " + field_path).c_str());
    }
    if (!f->getter) {
        throw nb::type_error(("No getter for field: " + field_path).c_str());
    }
    tc_value val = f->getter(obj);
    nb::object result = tc_value_to_nb(&val);
    tc_value_free(&val);
    return result;
}

void InspectRegistryPythonExt::set(InspectRegistry& reg, void* obj, const std::string& type_name,
                                   const std::string& field_path, nb::object value, void* context) {
    const InspectFieldInfo* f = reg.find_field(type_name, field_path);
    if (!f) {
        throw nb::attribute_error(("Field not found: " + field_path).c_str());
    }
    if (!f->setter) {
        throw nb::type_error(("No setter for field: " + field_path).c_str());
    }
    tc_value val = nb_to_tc_value(value);
    f->setter(obj, val, context);
    tc_value_free(&val);
}

void InspectRegistryPythonExt::deserialize_all_py(InspectRegistry& reg, void* obj,
                                                   const std::string& type_name,
                                                   const nb::dict& data, void* context) {
    for (const auto& f : reg.all_fields(type_name)) {
        if (!f.is_serializable) continue;
        if (!f.setter) continue;

        nb::str key(f.path.c_str());
        if (!data.contains(key)) continue;

        nb::object field_data = data[key];
        if (field_data.is_none()) continue;

        tc_value val = nb_to_tc_value(field_data);
        f.setter(obj, val, context);
        tc_value_free(&val);
    }
}

void InspectRegistryPythonExt::deserialize_component_fields_over_python(
    InspectRegistry& reg, void* ptr, nb::object obj, const std::string& type_name,
    const nb::dict& data, void* context) {
    // For C++ components ptr is the object, for Python components obj.ptr() is used
    void* target = (reg.get_type_backend(type_name) == TypeBackend::Cpp) ? ptr : obj.ptr();
    deserialize_all_py(reg, target, type_name, data, context);
}

} // namespace tc
