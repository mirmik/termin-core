// tc_inspect_cpp.hpp - Pure C++ inspection system (no Python/nanobind dependency)
// For external modules that don't link against nanobind.
// Use tc_inspect.hpp if you need Python interop.
#pragma once

#include "inspect/tc_inspect.h"
#include <tcbase/tc_log.h>
#include <string>
#include <vector>
#include <unordered_map>
#include <functional>
#include <any>
#include <memory>

#include "inspect/tc_kind_cpp.hpp"

namespace tc {

// ============================================================================
// TypeBackend - language/runtime that implements the type
// ============================================================================

enum class TypeBackend {
    Cpp,
    Python,
    Rust
};

// ============================================================================
// EnumChoice wrapper (C++ only, no nb::object)
// ============================================================================

struct EnumChoice {
    std::string value;
    std::string label;
};

struct InspectContext {
    void* context = nullptr;
    void* user_context = nullptr;
};

// ============================================================================
// InspectFieldInfo - field metadata + callbacks (C++ only)
// ============================================================================

struct InspectFieldInfo {
    std::string type_name;
    std::string path;
    std::string label;
    std::string kind;
    double min = 0.0;
    double max = 1.0;
    double step = 0.01;
    bool is_serializable = true;
    bool is_inspectable = true;
    std::vector<EnumChoice> choices;
    // Unified action callback with generic object pointer and optional context.
    std::function<void(void*, const InspectContext&)> action;

    // Unified getter/setter via tc_value
    std::function<tc_value(void*)> getter;
    std::function<void(void*, tc_value, void*)> setter;

    // Fill tc_field_info from this InspectFieldInfo
    void fill_c_info(tc_field_info* out) const {
        out->path = path.c_str();
        out->label = label.c_str();
        out->kind = kind.c_str();
        out->min = min;
        out->max = max;
        out->step = step;
        out->is_serializable = is_serializable;
        out->is_inspectable = is_inspectable;
        out->choices = nullptr;
        out->choice_count = 0;
    }
};

// ============================================================================
// InspectRegistry - C++ only version
// ============================================================================

#ifdef _WIN32
    #ifdef TERMIN_INSPECT_CPP_EXPORTS
        #define TC_INSPECT_API __declspec(dllexport)
    #else
        #define TC_INSPECT_API __declspec(dllimport)
    #endif
#else
    #define TC_INSPECT_API __attribute__((visibility("default")))
#endif

class TC_INSPECT_API InspectRegistry {
    friend class InspectRegistryPythonExt;

    std::unordered_map<std::string, std::vector<InspectFieldInfo>> _fields;
    std::unordered_map<std::string, TypeBackend> _type_backends;
    std::unordered_map<std::string, std::string> _type_parents;

public:
    static InspectRegistry& instance();

    // ========================================================================
    // Type backend registration
    // ========================================================================

    void set_type_backend(const std::string& type_name, TypeBackend backend) {
        _type_backends[type_name] = backend;
    }

    TypeBackend get_type_backend(const std::string& type_name) const {
        auto it = _type_backends.find(type_name);
        return it != _type_backends.end() ? it->second : TypeBackend::Cpp;
    }

    bool has_type(const std::string& type_name) const {
        return _type_backends.find(type_name) != _type_backends.end();
    }

    void set_type_parent(const std::string& type_name, const std::string& parent_name) {
        if (!parent_name.empty()) {
            _type_parents[type_name] = parent_name;
            if (_type_backends.find(type_name) == _type_backends.end()) {
                _type_backends[type_name] = TypeBackend::Cpp;
            }
        }
    }

    std::string get_type_parent(const std::string& type_name) const {
        auto it = _type_parents.find(type_name);
        return it != _type_parents.end() ? it->second : "";
    }

    void unregister_type(const std::string& type_name) {
        _fields.erase(type_name);
        _type_backends.erase(type_name);
        _type_parents.erase(type_name);
    }

    // ========================================================================
    // Kind handler access
    // ========================================================================

    bool has_kind_handler(const std::string& kind) const {
        return KindRegistryCpp::instance().has(kind);
    }

    // ========================================================================
    // Field registration (C++ types via template)
    // ========================================================================

    template<typename C, typename T>
    void add(const char* type_name, T C::*member,
             const char* path, const char* label, const char* kind_str,
             double min = 0.0, double max = 1.0, double step = 0.01)
    {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind_str;
        info.min = min;
        info.max = max;
        info.step = step;

        std::string kind_copy = kind_str;

        info.getter = [member, kind_copy](void* obj) -> tc_value {
            T val = static_cast<C*>(obj)->*member;
            return KindRegistryCpp::instance().serialize(kind_copy, std::any(val));
        };

        std::string type_copy = type_name;
        std::string path_copy = path;

        info.setter = [member, kind_copy, type_copy, path_copy](void* obj, tc_value value, void* context) {
            std::any val = KindRegistryCpp::instance().deserialize(kind_copy, &value, context);
            if (val.has_value()) {
                try {
                    static_cast<C*>(obj)->*member = std::any_cast<T>(val);
                } catch (const std::bad_any_cast& e) {
                    tc_log(TC_LOG_ERROR, "[Inspect] Field '%s.%s': kind '%s' returned incompatible type. "
                                   "Check that field type matches kind (e.g., 'double' field needs 'double' kind, not 'float')",
                                   type_copy.c_str(), path_copy.c_str(), kind_copy.c_str());
                }
            }
        };

        _fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
    }

    template<typename C, typename T>
    void add_with_callbacks(
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind_str,
        std::function<T&(C*)> getter_fn,
        std::function<void(C*, const T&)> setter_fn,
        double min_val = 0.0,
        double max_val = 1.0,
        double step_val = 0.01
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind_str;
        info.min = min_val;
        info.max = max_val;
        info.step = step_val;

        std::string kind_copy = kind_str;

        info.getter = [getter_fn, kind_copy](void* obj) -> tc_value {
            T val = getter_fn(static_cast<C*>(obj));
            return KindRegistryCpp::instance().serialize(kind_copy, std::any(val));
        };

        std::string type_copy = type_name;
        std::string path_copy = path;

        info.setter = [setter_fn, kind_copy, type_copy, path_copy](void* obj, tc_value value, void* context) {
            std::any val = KindRegistryCpp::instance().deserialize(kind_copy, &value, context);
            if (val.has_value()) {
                try {
                    setter_fn(static_cast<C*>(obj), std::any_cast<T>(val));
                } catch (const std::bad_any_cast& e) {
                    tc_log(TC_LOG_ERROR, "[Inspect] Field '%s.%s': kind '%s' returned incompatible type. "
                                   "Check that field type matches kind (e.g., 'double' field needs 'double' kind, not 'float')",
                                   type_copy.c_str(), path_copy.c_str(), kind_copy.c_str());
                }
            }
        };

        _fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
    }

    template<typename C, typename T>
    void add_with_accessors(
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind_str,
        std::function<T(C*)> getter_fn,
        std::function<void(C*, T)> setter_fn
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind_str;

        std::string kind_copy = kind_str;
        std::string type_copy = type_name;
        std::string path_copy = path;

        info.getter = [getter_fn, kind_copy](void* obj) -> tc_value {
            T val = getter_fn(static_cast<C*>(obj));
            return KindRegistryCpp::instance().serialize(kind_copy, std::any(val));
        };

        info.setter = [setter_fn, kind_copy, type_copy, path_copy](void* obj, tc_value value, void* context) {
            std::any val = KindRegistryCpp::instance().deserialize(kind_copy, &value, context);
            if (val.has_value()) {
                try {
                    setter_fn(static_cast<C*>(obj), std::any_cast<T>(val));
                } catch (const std::bad_any_cast& e) {
                    tc_log(TC_LOG_ERROR, "[Inspect] Field '%s.%s': kind '%s' returned incompatible type. "
                                   "Check that field type matches kind (e.g., 'double' field needs 'double' kind, not 'float')",
                                   type_copy.c_str(), path_copy.c_str(), kind_copy.c_str());
                }
            }
        };

        _fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
    }

    template<typename C, typename H>
    void add_handle(
        const char* type_name, H C::*member,
        const char* path, const char* label, const char* kind_str
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind_str;

        std::string kind_copy = kind_str;
        std::string type_copy = type_name;
        std::string path_copy = path;

        info.getter = [member, kind_copy](void* obj) -> tc_value {
            H val = static_cast<C*>(obj)->*member;
            return KindRegistryCpp::instance().serialize(kind_copy, std::any(val));
        };

        info.setter = [member, kind_copy, type_copy, path_copy](void* obj, tc_value value, void* context) {
            std::any val = KindRegistryCpp::instance().deserialize(kind_copy, &value, context);
            if (val.has_value()) {
                try {
                    static_cast<C*>(obj)->*member = std::any_cast<H>(val);
                } catch (const std::bad_any_cast& e) {
                    tc_log(TC_LOG_ERROR, "[Inspect] Field '%s.%s': kind '%s' returned incompatible type. "
                                   "Check that field type matches kind",
                                   type_copy.c_str(), path_copy.c_str(), kind_copy.c_str());
                }
            }
        };

        _fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
    }

    void add_serializable_field(const std::string& type_name, InspectFieldInfo&& info) {
        _fields[type_name].push_back(std::move(info));
    }

    void add_field_with_choices(const std::string& type_name, InspectFieldInfo&& info) {
        _fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
    }

    void add_button(const std::string& type_name, const std::string& path,
                    const std::string& label, std::function<void(void*, const InspectContext&)> action_fn) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = "button";
        info.is_serializable = false;
        info.is_inspectable = true;
        info.action = std::move(action_fn);

        _fields[type_name].push_back(std::move(info));
    }

    // ========================================================================
    // Field queries
    // ========================================================================

    const std::vector<InspectFieldInfo>& fields(const std::string& type_name) const {
        static std::vector<InspectFieldInfo> empty;
        auto it = _fields.find(type_name);
        return it != _fields.end() ? it->second : empty;
    }

    std::vector<InspectFieldInfo> all_fields(const std::string& type_name) const {
        std::vector<InspectFieldInfo> result;
        std::string parent = get_type_parent(type_name);
        if (!parent.empty()) {
            auto parent_fields = all_fields(parent);
            result.insert(result.end(), parent_fields.begin(), parent_fields.end());
        }
        auto it = _fields.find(type_name);
        if (it != _fields.end()) {
            result.insert(result.end(), it->second.begin(), it->second.end());
        }
        return result;
    }

    size_t all_fields_count(const std::string& type_name) const {
        size_t count = 0;
        std::string parent = get_type_parent(type_name);
        if (!parent.empty()) {
            count += all_fields_count(parent);
        }
        auto it = _fields.find(type_name);
        if (it != _fields.end()) {
            count += it->second.size();
        }
        return count;
    }

    const InspectFieldInfo* get_field_by_index(const std::string& type_name, size_t index) const {
        std::string parent = get_type_parent(type_name);
        if (!parent.empty()) {
            size_t parent_count = all_fields_count(parent);
            if (index < parent_count) {
                return get_field_by_index(parent, index);
            }
            index -= parent_count;
        }
        auto it = _fields.find(type_name);
        if (it != _fields.end() && index < it->second.size()) {
            return &it->second[index];
        }
        return nullptr;
    }

    const InspectFieldInfo* find_field(const std::string& type_name, const std::string& path) const {
        auto it = _fields.find(type_name);
        if (it != _fields.end()) {
            for (const auto& f : it->second) {
                if (f.path == path) return &f;
            }
        }
        std::string parent = get_type_parent(type_name);
        if (!parent.empty()) {
            return find_field(parent, path);
        }
        return nullptr;
    }

    std::vector<std::string> types() const {
        std::vector<std::string> result;
        for (const auto& [name, _] : _fields) {
            result.push_back(name);
        }
        return result;
    }

    // ========================================================================
    // Field access via tc_value
    // ========================================================================

    tc_value get_tc_value(void* obj, const std::string& type_name, const std::string& field_path) const {
        const InspectFieldInfo* f = find_field(type_name, field_path);
        if (!f || !f->getter) return tc_value_nil();
        return f->getter(obj);
    }

    void set_tc_value(void* obj, const std::string& type_name, const std::string& field_path, tc_value value, void* context) {
        const InspectFieldInfo* f = find_field(type_name, field_path);
        if (!f) {
            tc_log(TC_LOG_WARN, "[Inspect] Field '%s.%s' not found", type_name.c_str(), field_path.c_str());
            return;
        }
        if (!f->setter) {
            tc_log(TC_LOG_WARN, "[Inspect] Field '%s.%s' has no setter", type_name.c_str(), field_path.c_str());
            return;
        }
        f->setter(obj, value, context);
    }

    void action_field(void* obj, const std::string& type_name, const std::string& field_path,
                      const InspectContext& context = InspectContext{}) {
        const InspectFieldInfo* f = find_field(type_name, field_path);
        if (!f || !f->action) return;
        f->action(obj, context);
    }

    // ========================================================================
    // Serialization (C++ only, via tc_value)
    // ========================================================================

    tc_value serialize_all(void* obj, const std::string& type_name) const {
        tc_value result = tc_value_dict_new();
        for (const auto& f : all_fields(type_name)) {
            if (!f.is_serializable) continue;
            if (!f.getter) continue;
            tc_value val = f.getter(obj);
            if (val.type != TC_VALUE_NIL) {
                tc_value_dict_set(&result, f.path.c_str(), val);
            } else {
                tc_value_free(&val);
            }
        }
        return result;
    }

    void deserialize_all(void* obj, const std::string& type_name, const tc_value* data, void* context = nullptr) {
        if (!data || data->type != TC_VALUE_DICT) return;
        for (const auto& f : all_fields(type_name)) {
            if (!f.is_serializable) continue;
            if (!f.setter) continue;
            tc_value* field_val = tc_value_dict_get(const_cast<tc_value*>(data), f.path.c_str());
            if (!field_val || field_val->type == TC_VALUE_NIL) continue;
            f.setter(obj, *field_val, context);
        }
    }
};

// ============================================================================
// C++ vtable callbacks
// ============================================================================

TC_INSPECT_API void init_cpp_inspect_vtable();

// ============================================================================
// Static registration helpers
// ============================================================================

template<typename C, typename T>
struct InspectFieldRegistrar {
    InspectFieldRegistrar(T C::*member, const char* type_name,
                          const char* path, const char* label, const char* kind,
                          double min = 0.0, double max = 1.0, double step = 0.01) {
        InspectRegistry::instance().add<C, T>(type_name, member, path, label, kind, min, max, step);
    }
};

template<typename C, typename T>
struct InspectFieldCallbackRegistrar {
    InspectFieldCallbackRegistrar(
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind,
        std::function<T&(C*)> getter,
        std::function<void(C*, const T&)> setter,
        double min_val = 0.0,
        double max_val = 1.0,
        double step_val = 0.01
    ) {
        InspectRegistry::instance().add_with_callbacks<C, T>(
            type_name, path, label, kind, getter, setter, min_val, max_val, step_val
        );
    }
};

template<typename C, typename T>
struct InspectFieldChoicesRegistrar {
    InspectFieldChoicesRegistrar(
        T C::*member,
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind_str,
        std::initializer_list<std::pair<const char*, const char*>> choices_list
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind_str;

        for (const auto& [value, choice_label] : choices_list) {
            EnumChoice choice;
            choice.value = value;
            choice.label = choice_label;
            info.choices.push_back(std::move(choice));
        }

        std::string kind_copy = kind_str;
        std::string type_copy = type_name;
        std::string path_copy = path;

        info.getter = [member, kind_copy](void* obj) -> tc_value {
            T val = static_cast<C*>(obj)->*member;
            return KindRegistryCpp::instance().serialize(kind_copy, std::any(val));
        };

        info.setter = [member, kind_copy, type_copy, path_copy](void* obj, tc_value value, void* context) {
            std::any val = KindRegistryCpp::instance().deserialize(kind_copy, &value, context);
            if (val.has_value()) {
                try {
                    static_cast<C*>(obj)->*member = std::any_cast<T>(val);
                } catch (const std::bad_any_cast& e) {
                    tc_log(TC_LOG_ERROR, "[Inspect] Field '%s.%s': kind '%s' returned incompatible type. "
                                   "Check that field type matches kind (e.g., 'double' field needs 'double' kind, not 'float')",
                                   type_copy.c_str(), path_copy.c_str(), kind_copy.c_str());
                }
            }
        };

        InspectRegistry::instance().add_field_with_choices(type_name, std::move(info));
    }
};

template<typename C>
struct SerializableFieldRegistrar {
    SerializableFieldRegistrar(
        const char* type_name,
        const char* path,
        std::function<tc_value(C*)> tc_getter,
        std::function<void(C*, const tc_value*)> tc_setter
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = "";
        info.kind = "";
        info.is_inspectable = false;
        info.is_serializable = true;

        info.getter = [tc_getter](void* obj) -> tc_value {
            return tc_getter(static_cast<C*>(obj));
        };

        info.setter = [tc_setter](void* obj, tc_value value, void*) {
            tc_setter(static_cast<C*>(obj), &value);
        };

        InspectRegistry::instance().add_serializable_field(type_name, std::move(info));
    }
};

struct InspectButtonRegistrar {
    InspectButtonRegistrar(
        const char* type_name,
        const char* path,
        const char* label,
        std::function<void(void*, const tc::InspectContext&)> action_fn
    ) {
        InspectRegistry::instance().add_button(type_name, path, label, std::move(action_fn));
    }
};

} // namespace tc

// ============================================================================
// Macros
// ============================================================================

#define INSPECT_FIELD(cls, field, label, kind, ...) \
    inline static ::tc::InspectFieldRegistrar<cls, decltype(cls::field)> \
        _inspect_reg_##cls##_##field{&cls::field, #cls, #field, label, kind, ##__VA_ARGS__};

#define INSPECT_FIELD_RANGE(cls, field, label, kind, min_val, max_val) \
    inline static ::tc::InspectFieldRegistrar<cls, decltype(cls::field)> \
        _inspect_reg_##cls##_##field{&cls::field, #cls, #field, label, kind, min_val, max_val, 0.01};

#define INSPECT_FIELD_CALLBACK(cls, type, name, label, kind, getter_fn, setter_fn, ...) \
    inline static ::tc::InspectFieldCallbackRegistrar<cls, type> \
        _inspect_reg_##cls##_##name{#cls, #name, label, kind, getter_fn, setter_fn, ##__VA_ARGS__};

#define SERIALIZABLE_FIELD(cls, name, getter_expr, setter_expr) \
    inline static ::tc::SerializableFieldRegistrar<cls> \
        _serialize_reg_##cls##_##name{#cls, #name, \
            [](cls* self) -> tc_value { return self->getter_expr; }, \
            [](cls* self, const tc_value* val) { self->setter_expr; }};

#define INSPECT_FIELD_CHOICES(cls, field, label, kind, ...) \
    inline static ::tc::InspectFieldChoicesRegistrar<cls, decltype(cls::field)> \
        _inspect_reg_##cls##_##field{&cls::field, #cls, #field, label, kind, {__VA_ARGS__}};

#define INSPECT_BUTTON(cls, name, label, method) \
    inline static ::tc::InspectButtonRegistrar \
        _inspect_btn_##cls##_##name{#cls, #name, label, \
            [](void* obj, const ::tc::InspectContext&) { \
                auto* self = static_cast<cls*>(obj); \
                if (self) (self->*method)(); \
            }};
