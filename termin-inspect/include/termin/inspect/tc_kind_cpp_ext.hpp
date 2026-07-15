// tc_kind_cpp_ext.hpp - C++ helpers for registering handle kinds.
#pragma once

#include <optional>
#include <string>
#include <vector>

#include "inspect/tc_kind_cpp.hpp"

namespace tc {

template <typename>
inline constexpr bool always_false_v = false;

template<typename H>
tc_value serialize_handle_value(const H& h) {
    if constexpr (requires(const H& x) { x.serialize_to_value(); }) {
        return h.serialize_to_value();
    } else if constexpr (requires(const H& x) {
        x.is_valid();
        x.uuid();
        x.name();
    }) {
        tc_value d = tc_value_dict_new();
        if (h.is_valid()) {
            tc_value_dict_set(&d, "uuid", tc_value_string(h.uuid()));
            tc_value_dict_set(&d, "name", tc_value_string(h.name()));
        }
        return d;
    } else {
        static_assert(always_false_v<H>, "Handle type must provide serialize_to_value() or {is_valid, uuid, name}.");
    }
}

template<typename H>
H deserialize_handle_value(const tc_value* v, void* context) {
    if constexpr (requires(H x) { x.deserialize_from(v, context); }) {
        H h;
        h.deserialize_from(v, context);
        return h;
    } else if constexpr (requires { H::from_uuid(std::string()); }) {
        if (!v || v->type != TC_VALUE_DICT) {
            return H();
        }
        tc_value* uuid_val = tc_value_dict_get(const_cast<tc_value*>(v), "uuid");
        if (!uuid_val || uuid_val->type != TC_VALUE_STRING || !uuid_val->data.s) {
            return H();
        }
        return H::from_uuid(std::string(uuid_val->data.s));
    } else {
        static_assert(always_false_v<H>, "Handle type must provide deserialize_from() or static from_uuid().");
    }
}

template<typename H>
bool handle_value_is_valid(const H& value) {
    if constexpr (requires(const H& x) { x.valid(); }) {
        return value.valid();
    } else if constexpr (requires(const H& x) { x.is_valid(); }) {
        return value.is_valid();
    } else {
        return true;
    }
}

template<typename H>
std::optional<H> deserialize_handle_value_checked(const tc_value* value, void* context) {
    if (value == nullptr || value->type != TC_VALUE_DICT) return std::nullopt;
    tc_value* uuid = tc_value_dict_get(const_cast<tc_value*>(value), "uuid");
    if (uuid == nullptr) return H{}; // Canonical null handle.
    if (uuid->type != TC_VALUE_STRING || uuid->data.s == nullptr) return std::nullopt;
    if (uuid->data.s[0] == '\0') return H{};
    H result = deserialize_handle_value<H>(value, context);
    if (!handle_value_is_valid(result)) return std::nullopt;
    return result;
}

template<typename H>
void register_cpp_handle_kind(const std::string& kind_name) {
    KindRegistryCpp& registry = KindRegistryCpp::instance();
    registry.register_kind(kind_name,
        [](const std::any& value) -> tc_value {
            const H& h = std::any_cast<const H&>(value);
            return serialize_handle_value(h);
        },
        [](const tc_value* v, void* context) -> std::any {
            auto value = deserialize_handle_value_checked<H>(v, context);
            return value ? std::any(std::move(*value)) : std::any();
        }
    );
    registry.mark_handle_kind(kind_name);

    std::string list_kind = "list[" + kind_name + "]";
    registry.register_kind(list_kind,
        [](const std::any& value) -> tc_value {
            const auto& vec = std::any_cast<const std::vector<H>&>(value);
            tc_value result = tc_value_list_new();
            for (const auto& h : vec) {
                tc_value item = serialize_handle_value(h);
                tc_value_list_push(&result, item);
            }
            return result;
        },
        [](const tc_value* v, void* context) -> std::any {
            if (!v || v->type != TC_VALUE_LIST) return std::any();
            std::vector<H> vec;
            for (size_t i = 0; i < v->data.list.count; i++) {
                auto value = deserialize_handle_value_checked<H>(
                    &v->data.list.items[i], context);
                if (!value) return std::any();
                vec.push_back(std::move(*value));
            }
            return std::any(std::move(vec));
        }
    );
    registry.mark_handle_kind(list_kind);
}

} // namespace tc
