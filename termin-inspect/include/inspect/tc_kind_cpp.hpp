// tc_kind_cpp.hpp - C++ layer for kind serialization
// Works standalone without Python. Python support is in tc_kind_python.hpp.
#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <functional>
#include <any>

extern "C" {
#include "inspect/tc_inspect.h"
#include "inspect/tc_kind.h"
#include <tcbase/tc_log.h>
}

// DLL export/import macros for termin-inspect C++ core
#ifdef _WIN32
    #ifdef TERMIN_INSPECT_CPP_EXPORTS
        #define TC_KIND_CPP_API __declspec(dllexport)
    #else
        #define TC_KIND_CPP_API __declspec(dllimport)
    #endif
#else
    #define TC_KIND_CPP_API __attribute__((visibility("default")))
#endif

namespace tc {

// C++ kind handler - uses std::any and tc_value for serialization
struct KindCpp {
    std::string name;
    std::function<tc_value(const std::any&)> serialize;
    std::function<std::any(const tc_value*, void*)> deserialize;

    bool is_valid() const {
        return serialize && deserialize;
    }
};

// C++ Kind Registry - manages C++ serialization handlers
// This is separate from the C tc_kind_handler system.
// Python layer (KindPython) can be added on top.
class TC_KIND_CPP_API KindRegistryCpp {
    std::unordered_map<std::string, KindCpp> _kinds;

public:
    // Singleton - defined in tc_kind_cpp.cpp
    static KindRegistryCpp& instance();

    // Register C++ handler
    void register_kind(
        const std::string& name,
        std::function<tc_value(const std::any&)> serialize,
        std::function<std::any(const tc_value*, void*)> deserialize
    );

    // Get handler (returns nullptr if not found)
    KindCpp* get(const std::string& name);
    const KindCpp* get(const std::string& name) const;

    bool has(const std::string& name) const;

    // Get all registered kind names
    std::vector<std::string> kinds() const;

    // Serialize value (caller owns returned tc_value)
    tc_value serialize(const std::string& kind_name, const std::any& value) const;

    // Deserialize value
    std::any deserialize(const std::string& kind_name, const tc_value* data, void* context = nullptr) const;
};

// Helper to get int from tc_value (handles both INT and DOUBLE)
inline int tc_value_to_int(const tc_value* v) {
    if (v->type == TC_VALUE_INT) return static_cast<int>(v->data.i);
    if (v->type == TC_VALUE_DOUBLE) return static_cast<int>(v->data.d);
    if (v->type == TC_VALUE_FLOAT) return static_cast<int>(v->data.f);
    return 0;
}

// Helper to get double from tc_value
inline double tc_value_to_double(const tc_value* v) {
    if (v->type == TC_VALUE_DOUBLE) return v->data.d;
    if (v->type == TC_VALUE_FLOAT) return static_cast<double>(v->data.f);
    if (v->type == TC_VALUE_INT) return static_cast<double>(v->data.i);
    return 0.0;
}

// Helper to get string from tc_value
inline std::string tc_value_to_string(const tc_value* v) {
    if (v->type == TC_VALUE_STRING && v->data.s) return v->data.s;
    return "";
}

// Register builtin C++ kinds (bool, int, float, double, string)
inline void register_builtin_cpp_kinds() {
    auto& reg = KindRegistryCpp::instance();

    // bool
    reg.register_kind("bool",
        [](const std::any& v) { return tc_value_bool(std::any_cast<bool>(v)); },
        [](const tc_value* v, void*) -> std::any { return v->data.b; }
    );
    reg.register_kind("checkbox",
        [](const std::any& v) { return tc_value_bool(std::any_cast<bool>(v)); },
        [](const tc_value* v, void*) -> std::any { return v->data.b; }
    );

    // int
    reg.register_kind("int",
        [](const std::any& v) { return tc_value_int(std::any_cast<int>(v)); },
        [](const tc_value* v, void*) -> std::any { return tc_value_to_int(v); }
    );
    reg.register_kind("slider_int",
        [](const std::any& v) { return tc_value_int(std::any_cast<int>(v)); },
        [](const tc_value* v, void*) -> std::any { return tc_value_to_int(v); }
    );
    // enum (C++ uses int for enum-like fields with choices)
    reg.register_kind("enum",
        [](const std::any& v) { return tc_value_int(std::any_cast<int>(v)); },
        [](const tc_value* v, void*) -> std::any { return tc_value_to_int(v); }
    );

    // float
    reg.register_kind("float",
        [](const std::any& v) { return tc_value_float(std::any_cast<float>(v)); },
        [](const tc_value* v, void*) -> std::any { return static_cast<float>(tc_value_to_double(v)); }
    );
    reg.register_kind("slider",
        [](const std::any& v) { return tc_value_float(std::any_cast<float>(v)); },
        [](const tc_value* v, void*) -> std::any { return static_cast<float>(tc_value_to_double(v)); }
    );
    reg.register_kind("drag_float",
        [](const std::any& v) { return tc_value_float(std::any_cast<float>(v)); },
        [](const tc_value* v, void*) -> std::any { return static_cast<float>(tc_value_to_double(v)); }
    );

    // double
    reg.register_kind("double",
        [](const std::any& v) { return tc_value_double(std::any_cast<double>(v)); },
        [](const tc_value* v, void*) -> std::any { return tc_value_to_double(v); }
    );

    // string
    reg.register_kind("string",
        [](const std::any& v) { return tc_value_string(std::any_cast<std::string>(v).c_str()); },
        [](const tc_value* v, void*) -> std::any { return tc_value_to_string(v); }
    );
    reg.register_kind("text",
        [](const std::any& v) { return tc_value_string(std::any_cast<std::string>(v).c_str()); },
        [](const tc_value* v, void*) -> std::any { return tc_value_to_string(v); }
    );
    reg.register_kind("multiline_text",
        [](const std::any& v) { return tc_value_string(std::any_cast<std::string>(v).c_str()); },
        [](const tc_value* v, void*) -> std::any { return tc_value_to_string(v); }
    );
    reg.register_kind("clip_selector",
        [](const std::any& v) { return tc_value_string(std::any_cast<std::string>(v).c_str()); },
        [](const tc_value* v, void*) -> std::any { return tc_value_to_string(v); }
    );

    // agent_type (string-based, used for navmesh agent type selection)
    reg.register_kind("agent_type",
        [](const std::any& v) { return tc_value_string(std::any_cast<std::string>(v).c_str()); },
        [](const tc_value* v, void*) -> std::any { return tc_value_to_string(v); }
    );

    // vec3 - serialized as list [x, y, z], deserialized to TC_VALUE_VEC3
    reg.register_kind("vec3",
        [](const std::any& v) -> tc_value {
            // Serialize: vec3 → tc_value_vec3 (tc_value_to_trent will convert to list)
            auto vec = std::any_cast<tc_vec3>(v);
            return tc_value_vec3(vec);
        },
        [](const tc_value* v, void*) -> std::any {
            tc_vec3 result = {0, 0, 0};
            if (v->type == TC_VALUE_VEC3) {
                result = v->data.v3;
            } else if (v->type == TC_VALUE_LIST && v->data.list.count >= 3) {
                result.x = tc_value_to_double(&v->data.list.items[0]);
                result.y = tc_value_to_double(&v->data.list.items[1]);
                result.z = tc_value_to_double(&v->data.list.items[2]);
            }
            return result;
        }
    );

    // quat - serialized as list [w, x, y, z], deserialized to TC_VALUE_QUAT
    reg.register_kind("quat",
        [](const std::any& v) -> tc_value {
            auto q = std::any_cast<tc_quat>(v);
            return tc_value_quat(q);
        },
        [](const tc_value* v, void*) -> std::any {
            tc_quat result = {0, 0, 0, 1};
            if (v->type == TC_VALUE_QUAT) {
                result = v->data.q;
            }
            return result;
        }
    );
}

// Helper to register handle types that have serialize_to_value() and deserialize_from() methods
template<typename H>
void register_cpp_handle_kind(const std::string& kind_name);

} // namespace tc
