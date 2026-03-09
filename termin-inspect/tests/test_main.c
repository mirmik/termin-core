#include "inspect/tc_inspect.h"
#include "inspect/tc_kind.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            fprintf(stderr, "FAIL: %s\n", msg); \
            return 1; \
        } \
    } while (0)

typedef struct {
    int64_t value;
    int action_called;
} mock_dispatch_obj;

static bool mock_has_type(const char* type_name, void* ctx) {
    (void)ctx;
    return type_name && strcmp(type_name, "MockDispatchType") == 0;
}

static const char* mock_get_parent(const char* type_name, void* ctx) {
    (void)type_name;
    (void)ctx;
    return NULL;
}

static size_t mock_field_count(const char* type_name, void* ctx) {
    (void)ctx;
    if (!type_name || strcmp(type_name, "MockDispatchType") != 0) return 0;
    return 1;
}

static bool mock_get_field(const char* type_name, size_t index, tc_field_info* out, void* ctx) {
    (void)ctx;
    if (!out || !type_name || strcmp(type_name, "MockDispatchType") != 0 || index != 0) return false;
    out->path = "value";
    out->label = "Value";
    out->kind = "int";
    out->min = 0.0;
    out->max = 10000.0;
    out->step = 1.0;
    out->is_serializable = true;
    out->is_inspectable = true;
    out->choices = NULL;
    out->choice_count = 0;
    return true;
}

static bool mock_find_field(const char* type_name, const char* path, tc_field_info* out, void* ctx) {
    (void)ctx;
    if (!out || !type_name || !path) return false;
    if (strcmp(type_name, "MockDispatchType") != 0) return false;
    if (strcmp(path, "value") != 0) return false;
    return mock_get_field(type_name, 0, out, ctx);
}

static tc_value mock_get(void* obj, const char* type_name, const char* path, void* ctx) {
    (void)ctx;
    if (!obj || !type_name || !path) return tc_value_nil();
    if (strcmp(type_name, "MockDispatchType") != 0 || strcmp(path, "value") != 0) return tc_value_nil();
    return tc_value_int(((mock_dispatch_obj*)obj)->value);
}

static void mock_set(void* obj, const char* type_name, const char* path, tc_value value, void* context, void* ctx) {
    (void)context;
    (void)ctx;
    if (!obj || !type_name || !path) return;
    if (strcmp(type_name, "MockDispatchType") != 0 || strcmp(path, "value") != 0) return;
    if (value.type == TC_VALUE_INT) ((mock_dispatch_obj*)obj)->value = value.data.i;
}

static void mock_action(void* obj, const char* type_name, const char* path, void* ctx) {
    (void)ctx;
    if (!obj || !type_name || !path) return;
    if (strcmp(type_name, "MockDispatchType") != 0 || strcmp(path, "value") != 0) return;
    ((mock_dispatch_obj*)obj)->action_called = 1;
}

static int test_inspect_dispatcher(void) {
    tc_inspect_lang_vtable vtable = {
        mock_has_type,
        mock_get_parent,
        mock_field_count,
        mock_get_field,
        mock_find_field,
        mock_get,
        mock_set,
        mock_action,
        NULL
    };

    tc_inspect_set_lang_vtable(TC_INSPECT_LANG_C, &vtable);
    TEST_ASSERT(tc_inspect_has_type("MockDispatchType"), "type lookup");
    TEST_ASSERT(tc_inspect_field_count("MockDispatchType") == 1, "field count");

    mock_dispatch_obj obj = {11, 0};
    tc_value v = tc_inspect_get(&obj, "MockDispatchType", "value");
    TEST_ASSERT(v.type == TC_VALUE_INT && v.data.i == 11, "get");
    tc_value_free(&v);

    tc_value set_v = tc_value_int(77);
    tc_inspect_set(&obj, "MockDispatchType", "value", set_v, NULL);
    tc_value_free(&set_v);
    TEST_ASSERT(obj.value == 77, "set");

    tc_inspect_action(&obj, "MockDispatchType", "value");
    TEST_ASSERT(obj.action_called == 1, "action");

    tc_inspect_cleanup();
    return 0;
}

static int test_kind_parse(void) {
    char container[32];
    char element[32];
    bool ok = tc_kind_parse("list[entity_handle]", container, sizeof(container), element, sizeof(element));
    TEST_ASSERT(ok, "kind parse list");
    TEST_ASSERT(strcmp(container, "list") == 0, "container");
    TEST_ASSERT(strcmp(element, "entity_handle") == 0, "element");
    return 0;
}

int main(void) {
    if (test_inspect_dispatcher()) return 1;
    if (test_kind_parse()) return 1;
    printf("termin-inspect smoke tests: PASS\n");
    return 0;
}
