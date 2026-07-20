// tc_inspect_cpp.hpp - Pure C++ inspection system (no Python/nanobind dependency)
// For external modules that don't link against nanobind.
// Use tc_inspect.hpp if you need Python interop.
#pragma once

#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable: 4251) // STL members in dllexport classes
#endif

#include "inspect/tc_inspect.h"
#include <tcbase/tc_log.h>
#include <string>
#include <vector>
#include <unordered_map>
#include <functional>
#include <any>
#include <memory>
#include <type_traits>
#include <cstring>
#include <algorithm>
#include <utility>

#include "inspect/tc_kind_cpp.hpp"
#include "inspect/tc_runtime_type_registry.h"

namespace tc {

inline constexpr const char* TC_RUNTIME_TYPE_FACET_INSPECT_FIELDS = "termin.inspect.fields";

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

struct InspectFieldSpec {
    const char* type_name = "";
    const char* path = "";
    const char* label = "";
    const char* kind = "";
    double min = -1e9;
    double max = 1e9;
    double step = 0.01;
    bool is_serializable = true;
    bool is_inspectable = true;
};

// ============================================================================
// InspectFieldInfo - field metadata + callbacks (C++ only)
// ============================================================================

struct InspectFieldInfo {
    std::string type_name;
    std::string path;
    std::string label;
    std::string kind;
    double min = -1e9;
    double max = 1e9;
    double step = 0.01;
    bool is_serializable = true;
    bool is_inspectable = true;
    std::vector<EnumChoice> choices;
    // Unified action callback with generic object pointer and optional context.
    std::function<void(void*, const InspectContext&)> action;

    // Unified getter/setter via tc_value
    std::function<tc_value(void*)> getter;
    // Returns true only when the value was accepted and applied.  A nil
    // tc_value is a regular input value; failure is carried separately.
    std::function<bool(void*, tc_value, void*)> setter;

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

inline InspectFieldSpec inspect_field_spec(
    const char* type_name,
    const char* path,
    const char* label,
    const char* kind,
    double min = -1e9,
    double max = 1e9,
    double step = 0.01)
{
    return {type_name, path, label, kind, min, max, step};
}

inline InspectFieldSpec inspect_accessor_field_spec(
    const char* type_name,
    const char* path,
    const char* label,
    const char* kind,
    bool is_serializable = true,
    bool is_inspectable = true)
{
    InspectFieldSpec spec = inspect_field_spec(type_name, path, label, kind);
    spec.is_serializable = is_serializable;
    spec.is_inspectable = is_inspectable;
    return spec;
}

inline InspectFieldInfo make_inspect_field_info(const InspectFieldSpec& spec) {
    InspectFieldInfo info;
    info.type_name = spec.type_name ? spec.type_name : "";
    info.path = spec.path ? spec.path : "";
    info.label = spec.label ? spec.label : "";
    info.kind = spec.kind ? spec.kind : "";
    info.min = spec.min;
    info.max = spec.max;
    info.step = spec.step;
    info.is_serializable = spec.is_serializable;
    info.is_inspectable = spec.is_inspectable;
    return info;
}

#ifdef _WIN32
    #ifdef TERMIN_INSPECT_CPP_EXPORTS
        #define TC_INSPECT_API __declspec(dllexport)
    #else
        #define TC_INSPECT_API __declspec(dllimport)
    #endif
#else
    #define TC_INSPECT_API __attribute__((visibility("default")))
#endif

namespace detail {

struct InspectFacetPayload {
    std::string type_name;
    std::vector<InspectFieldInfo> fields;
    TypeBackend backend = TypeBackend::Cpp;
    bool has_backend = false;
    tc_value metadata;
    bool has_metadata = false;

    explicit InspectFacetPayload(std::string type_name_)
        : type_name(std::move(type_name_))
        , metadata(tc_value_nil()) {}

    InspectFacetPayload(const InspectFacetPayload& other)
        : type_name(other.type_name)
        , fields(other.fields)
        , backend(other.backend)
        , has_backend(other.has_backend)
        , metadata(other.has_metadata ? tc_value_copy(&other.metadata) : tc_value_nil())
        , has_metadata(other.has_metadata) {}

    InspectFacetPayload& operator=(const InspectFacetPayload&) = delete;

    ~InspectFacetPayload() {
        if (has_metadata) {
            tc_value_free(&metadata);
        }
    }
};

inline void destroy_inspect_facet(void* payload) {
    delete static_cast<InspectFacetPayload*>(payload);
}

} // namespace detail

// Builds a complete inspect facet without exposing it through the live runtime
// registry. attach_to() transfers the validated payload to a staged runtime
// type descriptor, so callbacks become visible only with descriptor commit.
class TC_INSPECT_API InspectFacetBuilder {
    std::unique_ptr<detail::InspectFacetPayload> _payload;
    std::string _error;

    bool reject(const std::string& message) {
        if (_error.empty()) {
            _error = message;
            tc_log(TC_LOG_ERROR, "[Inspect] InspectFacetBuilder rejected: %s", message.c_str());
        }
        return false;
    }

    bool validate_field(const InspectFieldInfo& info) {
        if (info.path.empty()) {
            return reject("field path must not be empty for type '" + type_name() + "'");
        }
        if (!info.type_name.empty() && info.type_name != type_name()) {
            return reject(
                "field '" + info.path + "' belongs to type '" + info.type_name +
                "', expected '" + type_name() + "'"
            );
        }
        if (info.kind == "button") {
            if (!info.action) {
                return reject(
                    "button field '" + type_name() + "." + info.path + "' has no action"
                );
            }
        } else if (!info.getter && !info.setter) {
            return reject(
                "field '" + type_name() + "." + info.path + "' has no callbacks"
            );
        } else if (info.is_serializable && !info.getter) {
            return reject(
                "serializable field '" + type_name() + "." + info.path + "' has no getter"
            );
        }
        return true;
    }

public:
    explicit InspectFacetBuilder(std::string type_name)
        : _payload(std::make_unique<detail::InspectFacetPayload>(std::move(type_name))) {
        if (_payload->type_name.empty()) {
            reject("type name must not be empty");
        }
    }

    InspectFacetBuilder(InspectFacetBuilder&&) noexcept = default;
    InspectFacetBuilder& operator=(InspectFacetBuilder&&) noexcept = default;
    InspectFacetBuilder(const InspectFacetBuilder&) = delete;
    InspectFacetBuilder& operator=(const InspectFacetBuilder&) = delete;

    const std::string& type_name() const {
        static const std::string empty;
        return _payload ? _payload->type_name : empty;
    }

    bool valid() const { return _payload && _error.empty(); }
    const std::string& error() const { return _error; }

    const InspectFieldInfo* find_field(const std::string& path) const {
        if (!_payload) return nullptr;
        for (const InspectFieldInfo& field : _payload->fields) {
            if (field.path == path) return &field;
        }
        return nullptr;
    }

    const InspectFieldInfo* find_field(
        const std::string& requested_type,
        const std::string& path
    ) const {
        if (requested_type != type_name()) return nullptr;
        return find_field(path);
    }

    bool set_backend(TypeBackend backend) {
        if (!valid()) return false;
        switch (backend) {
            case TypeBackend::Cpp:
            case TypeBackend::Python:
            case TypeBackend::Rust:
                _payload->backend = backend;
                _payload->has_backend = true;
                return true;
        }
        return reject("invalid backend for type '" + type_name() + "'");
    }

    bool set_metadata(const tc_value* metadata) {
        if (!valid()) return false;
        if (metadata && metadata->type != TC_VALUE_DICT) {
            return reject("metadata for type '" + type_name() + "' must be a dictionary");
        }
        if (_payload->has_metadata) {
            tc_value_free(&_payload->metadata);
        }
        _payload->metadata = metadata ? tc_value_copy(metadata) : tc_value_dict_new();
        _payload->has_metadata = true;
        return true;
    }

    bool set_metadata_key(const std::string& key, const tc_value* value) {
        if (!valid()) return false;
        if (key.empty()) {
            return reject("metadata key for type '" + type_name() + "' must not be empty");
        }
        if (!_payload->has_metadata) {
            _payload->metadata = tc_value_dict_new();
            _payload->has_metadata = true;
        }
        tc_value_dict_set(
            &_payload->metadata,
            key.c_str(),
            value ? tc_value_copy(value) : tc_value_nil()
        );
        return true;
    }

    bool add_field(InspectFieldInfo info) {
        if (!valid() || !validate_field(info)) return false;
        for (const InspectFieldInfo& existing : _payload->fields) {
            if (existing.path == info.path) {
                return reject(
                    "duplicate field path '" + type_name() + "." + info.path + "'"
                );
            }
        }
        info.type_name = type_name();
        _payload->fields.push_back(std::move(info));
        return true;
    }

    template<typename C, typename T>
    bool add(T C::*member, const InspectFieldSpec& spec) {
        InspectFieldInfo info = make_inspect_field_info(spec);
        const std::string kind = info.kind;
        const std::string type = type_name();
        const std::string path = info.path;
        info.getter = [member, kind, type, path](void* obj) -> tc_value {
            T value = static_cast<C*>(obj)->*member;
            return KindRegistryCpp::instance().serialize_field(
                kind, std::any(value), type, path
            );
        };
        info.setter = [member, kind, type, path](
            void* obj,
            tc_value value,
            void* context
        ) -> bool {
            std::any decoded = KindRegistryCpp::instance().deserialize(kind, &value, context);
            if (!decoded.has_value()) return false;
            try {
                static_cast<C*>(obj)->*member = std::any_cast<T>(decoded);
                return true;
            } catch (const std::bad_any_cast&) {
                tc_log(
                    TC_LOG_ERROR,
                    "[Inspect] Field '%s.%s' kind '%s' returned incompatible type",
                    type.c_str(),
                    path.c_str(),
                    kind.c_str()
                );
                return false;
            }
        };
        return add_field(std::move(info));
    }

    template<typename C, typename T, typename... RangeArgs>
    bool add(
        const char* type_name,
        T C::*member,
        const char* path,
        const char* label,
        const char* kind,
        RangeArgs&&... range_args
    ) {
        return add<C, T>(member, inspect_field_spec(
            type_name, path, label, kind, std::forward<RangeArgs>(range_args)...));
    }

    template<typename C, typename T, typename GetterFn, typename SetterFn>
    bool add_with_callbacks(
        const InspectFieldSpec& spec,
        GetterFn getter_fn,
        SetterFn setter_fn
    ) {
        return add_with_callbacks<C, T>(
            spec.type_name, spec.path, spec.label, spec.kind,
            std::move(getter_fn), std::move(setter_fn), spec.min, spec.max, spec.step);
    }

    template<typename C, typename T, typename GetterFn, typename SetterFn, typename... RangeArgs>
    bool add_with_callbacks(
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind,
        GetterFn getter_fn,
        SetterFn setter_fn,
        RangeArgs&&... range_args
    ) {
        InspectFieldInfo info = make_inspect_field_info(inspect_field_spec(
            type_name, path, label, kind, std::forward<RangeArgs>(range_args)...));
        const std::string kind_copy = info.kind;
        const std::string type_copy = this->type_name();
        const std::string path_copy = info.path;
        info.getter = [getter_fn = std::move(getter_fn), kind_copy, type_copy, path_copy](void* obj) {
            T value = getter_fn(static_cast<C*>(obj));
            return KindRegistryCpp::instance().serialize_field(
                kind_copy, std::any(value), type_copy, path_copy);
        };
        info.setter = [setter_fn = std::move(setter_fn), kind_copy, type_copy, path_copy](
            void* obj, tc_value value, void* context) -> bool {
            std::any decoded = KindRegistryCpp::instance().deserialize(kind_copy, &value, context);
            if (!decoded.has_value()) return false;
            try {
                setter_fn(static_cast<C*>(obj), std::any_cast<T>(decoded));
                return true;
            } catch (const std::bad_any_cast&) {
                tc_log(TC_LOG_ERROR, "[Inspect] staged field '%s.%s' kind '%s' returned incompatible type",
                       type_copy.c_str(), path_copy.c_str(), kind_copy.c_str());
                return false;
            }
        };
        return add_field(std::move(info));
    }

    template<typename C, typename T, typename GetterFn, typename SetterFn, typename... FlagArgs>
    bool add_with_accessors(
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind,
        GetterFn getter_fn,
        SetterFn setter_fn,
        FlagArgs&&... flag_args
    ) {
        InspectFieldSpec spec = inspect_accessor_field_spec(
            type_name, path, label, kind, std::forward<FlagArgs>(flag_args)...);
        InspectFieldInfo info = make_inspect_field_info(spec);
        const std::string kind_copy = info.kind;
        const std::string type_copy = this->type_name();
        const std::string path_copy = info.path;
        info.getter = [getter_fn = std::move(getter_fn), kind_copy, type_copy, path_copy](void* obj) {
            T value = getter_fn(static_cast<C*>(obj));
            return KindRegistryCpp::instance().serialize_field(
                kind_copy, std::any(value), type_copy, path_copy);
        };
        info.setter = [setter_fn = std::move(setter_fn), kind_copy](
            void* obj, tc_value value, void* context) -> bool {
            std::any decoded = KindRegistryCpp::instance().deserialize(kind_copy, &value, context);
            if (!decoded.has_value()) return false;
            try {
                setter_fn(static_cast<C*>(obj), std::any_cast<T>(decoded));
                return true;
            } catch (const std::bad_any_cast&) {
                return false;
            }
        };
        return add_field(std::move(info));
    }

    template<typename C, typename GetterFn, typename SetterFn>
    bool add_serializable(
        const char* path,
        GetterFn getter_fn,
        SetterFn setter_fn
    ) {
        InspectFieldInfo info;
        info.path = path;
        info.label = path;
        info.is_inspectable = false;
        info.getter = [getter_fn = std::move(getter_fn)](void* obj) {
            return getter_fn(static_cast<C*>(obj));
        };
        info.setter = [setter_fn = std::move(setter_fn)](
            void* obj, tc_value value, void*) -> bool {
            setter_fn(static_cast<C*>(obj), &value);
            return true;
        };
        return add_field(std::move(info));
    }

    template<typename C, typename T, typename GetterFn, typename SetterFn>
    bool add_with_accessor_choices(
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind,
        GetterFn getter_fn,
        SetterFn setter_fn,
        std::initializer_list<std::pair<const char*, const char*>> choices
    ) {
        InspectFieldInfo info = make_inspect_field_info(
            inspect_field_spec(type_name, path, label, kind));
        for (const auto& [value, choice_label] : choices) {
            info.choices.push_back(EnumChoice{value, choice_label});
        }
        const std::string kind_copy = info.kind;
        const std::string type_copy = this->type_name();
        const std::string path_copy = info.path;
        info.getter = [getter_fn = std::move(getter_fn), kind_copy, type_copy, path_copy](void* obj) {
            T value = getter_fn(static_cast<C*>(obj));
            return KindRegistryCpp::instance().serialize_field(
                kind_copy, std::any(value), type_copy, path_copy);
        };
        info.setter = [setter_fn = std::move(setter_fn), kind_copy](
            void* obj, tc_value value, void* context) -> bool {
            std::any decoded = KindRegistryCpp::instance().deserialize(kind_copy, &value, context);
            if (!decoded.has_value()) return false;
            try {
                setter_fn(static_cast<C*>(obj), std::any_cast<T>(decoded));
                return true;
            } catch (const std::bad_any_cast&) {
                return false;
            }
        };
        return add_field(std::move(info));
    }

    bool add_button(
        std::string path,
        std::string label,
        std::function<void(void*, const InspectContext&)> action
    ) {
        InspectFieldInfo info;
        info.type_name = type_name();
        info.path = std::move(path);
        info.label = std::move(label);
        info.kind = "button";
        info.is_serializable = false;
        info.action = std::move(action);
        return add_field(std::move(info));
    }

    bool attach_to(tc_runtime_type_descriptor* descriptor) {
        if (!descriptor) {
            return reject("cannot attach type '" + type_name() + "' to a null descriptor");
        }
        if (!valid()) return false;
        if (!_payload->has_backend) {
            _payload->backend = TypeBackend::Cpp;
            _payload->has_backend = true;
        }
        detail::InspectFacetPayload* payload = _payload.release();
        return tc_runtime_type_descriptor_add_facet(
            descriptor,
            TC_RUNTIME_TYPE_FACET_INSPECT_FIELDS,
            payload,
            detail::destroy_inspect_facet,
            nullptr,
            1
        );
    }

private:
    friend class InspectRegistry;
    friend class InspectRegistryPythonExt;

    explicit InspectFacetBuilder(const detail::InspectFacetPayload& payload)
        : _payload(std::make_unique<detail::InspectFacetPayload>(payload)) {}

    bool upsert_field(InspectFieldInfo info) {
        if (!valid() || !validate_field(info)) return false;
        info.type_name = type_name();
        for (InspectFieldInfo& existing : _payload->fields) {
            if (existing.path == info.path) {
                existing = std::move(info);
                return true;
            }
        }
        _payload->fields.push_back(std::move(info));
        return true;
    }

    std::unique_ptr<detail::InspectFacetPayload> release_payload() {
        return std::move(_payload);
    }
};

// ============================================================================
// InspectRegistry - C++ only version
// ============================================================================

class TC_INSPECT_API InspectRegistry {
    friend class InspectRegistryPythonExt;

    using InspectFacetPayload = detail::InspectFacetPayload;

    InspectFacetPayload* inspect_facet(const std::string& type_name) const {
        return static_cast<InspectFacetPayload*>(
            tc_runtime_type_registry_get_facet(
                type_name.c_str(),
                TC_RUNTIME_TYPE_FACET_INSPECT_FIELDS)
        );
    }

public:
    static InspectRegistry& instance();

    ~InspectRegistry() = default;

    // ========================================================================
    // Type backend registration
    // ========================================================================

    TypeBackend get_type_backend(const std::string& type_name) const {
        const InspectFacetPayload* payload = inspect_facet(type_name);
        return payload && payload->has_backend ? payload->backend : TypeBackend::Cpp;
    }

    bool has_type(const std::string& type_name) const {
        return tc_runtime_type_registry_has_facet(
            type_name.c_str(),
            TC_RUNTIME_TYPE_FACET_INSPECT_FIELDS);
    }

    std::string get_type_parent(const std::string& type_name) const {
        const char* parent = tc_runtime_type_registry_get_parent(type_name.c_str());
        return parent ? std::string(parent) : std::string();
    }

    std::string owner_of(const std::string& type_name) const {
        const char* owner = tc_runtime_type_registry_get_owner(type_name.c_str());
        return owner ? std::string(owner) : std::string();
    }

    size_t unregister_owner(const std::string& owner) {
        if (owner.empty()) {
            return 0;
        }
        return tc_runtime_type_registry_unregister_owner(owner.c_str());
    }

    tc_value type_metadata(const std::string& type_name) const {
        std::string parent = get_type_parent(type_name);
        if (!parent.empty()) {
            tc_value result = type_metadata(parent);
            const InspectFacetPayload* payload = inspect_facet(type_name);
            if (payload && payload->has_metadata && payload->metadata.type == TC_VALUE_DICT && result.type == TC_VALUE_DICT) {
                for (size_t i = 0; i < payload->metadata.data.dict.count; i++) {
                    const char* key = nullptr;
                    tc_value* value = tc_value_dict_get_at(const_cast<tc_value*>(&payload->metadata), i, &key);
                    if (key && value) {
                        tc_value_dict_set(&result, key, tc_value_copy(value));
                    }
                }
                return result;
            }
            if (payload && payload->has_metadata) {
                tc_value_free(&result);
                return tc_value_copy(&payload->metadata);
            }
            return result;
        }
        const InspectFacetPayload* payload = inspect_facet(type_name);
        if (payload && payload->has_metadata) {
            return tc_value_copy(&payload->metadata);
        }
        return tc_value_dict_new();
    }

    // ========================================================================
    // Kind handler access
    // ========================================================================

    bool has_kind_handler(const std::string& kind) const {
        return KindRegistryCpp::instance().has(kind);
    }

    // ========================================================================
    // Field queries
    // ========================================================================

    const std::vector<InspectFieldInfo>& fields(const std::string& type_name) const {
        static std::vector<InspectFieldInfo> empty;
        const InspectFacetPayload* payload = inspect_facet(type_name);
        return payload ? payload->fields : empty;
    }

    std::vector<InspectFieldInfo> all_fields(const std::string& type_name) const {
        std::vector<InspectFieldInfo> result;
        std::string parent = get_type_parent(type_name);
        if (!parent.empty()) {
            auto parent_fields = all_fields(parent);
            result.insert(result.end(), parent_fields.begin(), parent_fields.end());
        }
        const InspectFacetPayload* payload = inspect_facet(type_name);
        if (payload) {
            result.insert(result.end(), payload->fields.begin(), payload->fields.end());
        }
        return result;
    }

    size_t all_fields_count(const std::string& type_name) const {
        size_t count = 0;
        std::string parent = get_type_parent(type_name);
        if (!parent.empty()) {
            count += all_fields_count(parent);
        }
        const InspectFacetPayload* payload = inspect_facet(type_name);
        if (payload) {
            count += payload->fields.size();
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
        const InspectFacetPayload* payload = inspect_facet(type_name);
        if (payload && index < payload->fields.size()) {
            return &payload->fields[index];
        }
        return nullptr;
    }

    const InspectFieldInfo* find_field(const std::string& type_name, const std::string& path) const {
        const InspectFacetPayload* payload = inspect_facet(type_name);
        if (payload) {
            for (const auto& f : payload->fields) {
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
        tc_runtime_type_registry_foreach_type_with_facet(
            TC_RUNTIME_TYPE_FACET_INSPECT_FIELDS,
            [](const char* type_name, void* user_data) -> bool {
                static_cast<std::vector<std::string>*>(user_data)->emplace_back(type_name);
                return true;
            },
            &result);
        std::sort(result.begin(), result.end());
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

    bool set_tc_value(void* obj, const std::string& type_name, const std::string& field_path, tc_value value, void* context) {
        const InspectFieldInfo* f = find_field(type_name, field_path);
        if (!f) {
            tc_log(TC_LOG_WARN, "[Inspect] Field '%s.%s' not found", type_name.c_str(), field_path.c_str());
            return false;
        }
        if (!f->setter) {
            tc_log(TC_LOG_WARN, "[Inspect] Field '%s.%s' has no setter", type_name.c_str(), field_path.c_str());
            return false;
        }
        return f->setter(obj, value, context);
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
bool stage_inspect_field(
    InspectFacetBuilder& builder,
    T C::*member,
    const InspectFieldSpec& spec
) {
    return builder.add<C, T>(member, spec);
}

template<typename C, typename T, typename... RangeArgs>
bool stage_inspect_field(
    InspectFacetBuilder& builder,
    T C::*member,
    const char* type_name,
    const char* path,
    const char* label,
    const char* kind,
    RangeArgs&&... range_args)
{
    return stage_inspect_field<C, T>(
        builder,
        member,
        inspect_field_spec(
            type_name,
            path,
            label,
            kind,
            std::forward<RangeArgs>(range_args)...));
}

template<typename C, typename T>
bool stage_inspect_field_choices(
    InspectFacetBuilder& builder,
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
        info.choices.push_back(EnumChoice{value, choice_label});
    }
    std::string kind_copy = kind_str;
    std::string type_copy = type_name;
    std::string path_copy = path;
    info.getter = [member, kind_copy, type_copy, path_copy](void* obj) -> tc_value {
        T val = static_cast<C*>(obj)->*member;
        if constexpr (std::is_same_v<std::decay_t<T>, std::string>) {
            if (kind_copy == "enum") return tc_value_string(val.c_str());
        }
        return KindRegistryCpp::instance().serialize_field(
            kind_copy, std::any(val), type_copy, path_copy);
    };
    info.setter = [member, kind_copy, type_copy, path_copy](
        void* obj, tc_value value, void* context) -> bool {
        if constexpr (std::is_same_v<std::decay_t<T>, std::string>) {
            if (kind_copy == "enum") {
                static_cast<C*>(obj)->*member = value.type == TC_VALUE_STRING
                    ? tc_value_to_string(&value)
                    : std::to_string(tc_value_to_int(&value));
                return true;
            }
        }
        std::any val = KindRegistryCpp::instance().deserialize(kind_copy, &value, context);
        if (!val.has_value()) return false;
        try {
            static_cast<C*>(obj)->*member = std::any_cast<T>(val);
            return true;
        } catch (const std::bad_any_cast&) {
            tc_log(
                TC_LOG_ERROR,
                "[Inspect] staged field '%s.%s' kind '%s' returned incompatible type",
                type_copy.c_str(), path_copy.c_str(), kind_copy.c_str());
            return false;
        }
    };
    return builder.add_field(std::move(info));
}

template<typename C>
bool stage_inspect_button_method(
    InspectFacetBuilder& builder,
    const char* path,
    const char* label,
    void (C::*method)()
) {
    return builder.add_button(path, label, [method](void* obj, const InspectContext&) {
        auto* self = static_cast<C*>(obj);
        if (self) (self->*method)();
    });
}

} // namespace tc

// ============================================================================
// Macros
// ============================================================================

#define INSPECT_FIELD(cls, field, label, kind, ...) \
    static void _register_inspect_##field(::tc::InspectFacetBuilder& builder) { \
        (void)::tc::stage_inspect_field<cls, decltype(cls::field)>( \
            builder, &cls::field, ::tc::InspectFieldSpec{#cls, #field, label, kind, ##__VA_ARGS__}); \
    }

#define INSPECT_FIELD_RANGE(cls, field, label, kind, min_val, max_val) \
    static void _register_inspect_##field(::tc::InspectFacetBuilder& builder) { \
        (void)::tc::stage_inspect_field<cls, decltype(cls::field)>( \
            builder, &cls::field, ::tc::InspectFieldSpec{#cls, #field, label, kind, min_val, max_val, 0.01}); \
    }

#define INSPECT_FIELD_NAMED(cls, field, path, label, kind, ...) \
    static void _register_inspect_##field(::tc::InspectFacetBuilder& builder) { \
        (void)::tc::stage_inspect_field<cls, decltype(cls::field)>( \
            builder, &cls::field, ::tc::InspectFieldSpec{#cls, path, label, kind, ##__VA_ARGS__}); \
    }

#define INSPECT_FIELD_CALLBACK(cls, type, name, label, kind, getter_fn, setter_fn, ...) \
    static void _register_inspect_##name(::tc::InspectFacetBuilder& builder) { \
        (void)builder.add_with_callbacks<cls, type>( \
            ::tc::InspectFieldSpec{#cls, #name, label, kind, ##__VA_ARGS__}, getter_fn, setter_fn); \
    }

#define INSPECT_FIELD_ACCESSORS(cls, type, name, label, kind, getter_fn, setter_fn, ...) \
    static void _register_inspect_##name(::tc::InspectFacetBuilder& builder) { \
        (void)builder.add_with_accessors<cls, type>( \
            #cls, #name, label, kind, getter_fn, setter_fn, ##__VA_ARGS__); \
    }

#define INSPECT_FIELD_ACCESSORS_CHOICES(cls, type, name, label, kind, getter_fn, setter_fn, ...) \
    static void _register_inspect_##name(::tc::InspectFacetBuilder& builder) { \
        (void)builder.add_with_accessor_choices<cls, type>( \
            #cls, #name, label, kind, getter_fn, setter_fn, {__VA_ARGS__}); \
    }

#define SERIALIZABLE_FIELD(cls, name, getter_expr, setter_expr) \
    inline void register_serialize_##cls##_##name(::tc::InspectFacetBuilder& builder) { \
        ::tc::InspectFieldInfo info; \
        info.type_name = #cls; \
        info.path = #name; \
        info.label = #name; \
        info.is_inspectable = false; \
        info.getter = [](void* obj) -> tc_value { return static_cast<cls*>(obj)->getter_expr; }; \
        info.setter = [](void* obj, tc_value value, void*) -> bool { \
            const tc_value* val = &value; \
            static_cast<cls*>(obj)->setter_expr; \
            return true; \
        }; \
        (void)builder.add_field(std::move(info)); \
    }

#define INSPECT_FIELD_CHOICES(cls, field, label, kind, ...) \
    static void _register_inspect_##field(::tc::InspectFacetBuilder& builder) { \
        (void)::tc::stage_inspect_field_choices<cls, decltype(cls::field)>( \
            builder, &cls::field, #cls, #field, label, kind, {__VA_ARGS__}); \
    }

#define INSPECT_BUTTON(cls, name, label, method) \
    static void _register_inspect_##name(::tc::InspectFacetBuilder& builder) { \
        (void)::tc::stage_inspect_button_method<cls>(builder, #name, label, method); \
    }

#define INSPECT_TYPE_METADATA(cls, name, value_expr) \
    static void _register_inspect_metadata_##name(::tc::InspectFacetBuilder& builder) { \
        tc_value value = (value_expr); \
        (void)builder.set_metadata_key(#name, &value); \
        tc_value_free(&value); \
    }

#ifdef _MSC_VER
#pragma warning(pop)
#endif
