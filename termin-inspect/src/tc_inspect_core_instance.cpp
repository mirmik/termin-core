// tc_inspect_core_instance.cpp - Inspect core singleton, vtable wiring, and core init
// Compiled into termin-inspect to keep a single core instance.

#include "tc_inspect_cpp.hpp"
#include "inspect/tc_kind_cpp.hpp"

#include <string>

namespace tc {

InspectRegistry& InspectRegistry::instance() {
    static InspectRegistry reg;
    return reg;
}

static bool cpp_has_type(const char* type_name, void* ctx) {
    (void)ctx;
    return InspectRegistry::instance().has_type(type_name);
}

static const char* cpp_get_parent(const char* type_name, void* ctx) {
    (void)ctx;
    static std::string parent;
    parent = InspectRegistry::instance().get_type_parent(type_name);
    return parent.empty() ? nullptr : parent.c_str();
}

static size_t cpp_field_count(const char* type_name, void* ctx) {
    (void)ctx;
    return InspectRegistry::instance().all_fields_count(type_name);
}

static bool cpp_get_field(const char* type_name, size_t index, tc_field_info* out, void* ctx) {
    (void)ctx;
    const InspectFieldInfo* info = InspectRegistry::instance().get_field_by_index(type_name, index);
    if (!info) return false;
    info->fill_c_info(out);
    return true;
}

static bool cpp_find_field(const char* type_name, const char* path, tc_field_info* out, void* ctx) {
    (void)ctx;
    const InspectFieldInfo* info = InspectRegistry::instance().find_field(type_name, path);
    if (!info) return false;
    info->fill_c_info(out);
    return true;
}

static tc_value cpp_get(void* obj, const char* type_name, const char* path, void* ctx) {
    (void)ctx;
    return InspectRegistry::instance().get_tc_value(obj, type_name, path);
}

static void cpp_set(void* obj, const char* type_name, const char* path, tc_value value, void* context, void* ctx) {
    (void)ctx;
    InspectRegistry::instance().set_tc_value(obj, type_name, path, value, context);
}

static void cpp_action(void* obj, const char* type_name, const char* path, void* ctx) {
    (void)ctx;
    InspectContext inspect_context;
    InspectRegistry::instance().action_field(obj, type_name, path, inspect_context);
}

static bool g_cpp_vtable_initialized = false;

void init_cpp_inspect_vtable() {
    if (g_cpp_vtable_initialized) return;
    g_cpp_vtable_initialized = true;

    static tc_inspect_lang_vtable cpp_vtable = {
        cpp_has_type,
        cpp_get_parent,
        cpp_field_count,
        cpp_get_field,
        cpp_find_field,
        cpp_get,
        cpp_set,
        cpp_action,
        nullptr
    };

    tc_inspect_set_lang_vtable(TC_INSPECT_LANG_CPP, &cpp_vtable);
}

} // namespace tc

extern "C" {

void tc_inspect_kind_core_init(void) {
    tc::init_cpp_inspect_vtable();
    (void)tc::KindRegistryCpp::instance();
}

void tc_inspect_python_adapter_init(void) {
    // Python adapter wiring is owned by consumer layer.
}

void tc_init_full(void) {
    // Compatibility wrapper kept for legacy callers.
    // In extracted architecture this initializes inspect/kind core only.
    tc_inspect_kind_core_init();
    tc_inspect_python_adapter_init();
}

} // extern "C"
