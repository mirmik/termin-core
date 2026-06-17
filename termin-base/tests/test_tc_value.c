#include <math.h>
#include <string.h>

#include "guard_c.h"

#include <tcbase/tc_dlist.h>
#include <tcbase/tc_types.h>
#include <tcbase/tc_value.h>

typedef struct {
    int value;
    tc_dlist_node node;
} ListItem;

GUARD_C_TEST(test_tc_dlist) {
    tc_dlist_head list;
    tc_dlist_init_head(&list);
    GUARD_C_CHECK(tc_dlist_empty(&list));

    ListItem a = {.value = 10};
    ListItem b = {.value = 20};
    tc_dlist_init_node(&a.node);
    tc_dlist_init_node(&b.node);

    tc_dlist_add_tail(&a.node, &list);
    tc_dlist_add_tail(&b.node, &list);
    GUARD_C_CHECK_EQ_SIZE(2, tc_dlist_size(&list));
    GUARD_C_CHECK(tc_dlist_contains(&list, &a.node));

    ListItem* first = tc_dlist_first_entry(&list, ListItem, node);
    ListItem* last = tc_dlist_last_entry(&list, ListItem, node);
    GUARD_C_REQUIRE(first != NULL);
    GUARD_C_CHECK_EQ_INT(10, first->value);
    GUARD_C_REQUIRE(last != NULL);
    GUARD_C_CHECK_EQ_INT(20, last->value);

    tc_dlist_del(&a.node);
    GUARD_C_CHECK_EQ_SIZE(1, tc_dlist_size(&list));
    GUARD_C_CHECK_FALSE(tc_dlist_contains(&list, &a.node));
    return 0;
}

GUARD_C_TEST(test_tc_value) {
    tc_value v_nil = tc_value_nil();
    GUARD_C_CHECK(v_nil.type == TC_VALUE_NIL);

    tc_value v_bool = tc_value_bool(true);
    GUARD_C_CHECK(v_bool.type == TC_VALUE_BOOL);
    GUARD_C_CHECK(v_bool.data.b);

    tc_value v_int = tc_value_int(42);
    GUARD_C_CHECK(v_int.type == TC_VALUE_INT);
    GUARD_C_CHECK(v_int.data.i == 42);

    tc_value v_str = tc_value_string("hello");
    GUARD_C_CHECK(v_str.type == TC_VALUE_STRING);
    GUARD_C_CHECK_STREQ("hello", v_str.data.s);
    tc_value_free(&v_str);

    tc_value list = tc_value_list_new();
    tc_value_list_push(&list, tc_value_int(1));
    tc_value_list_push(&list, tc_value_int(2));
    tc_value_list_push(&list, tc_value_int(3));
    GUARD_C_CHECK_EQ_SIZE(3, tc_value_list_size(&list));
    GUARD_C_CHECK(tc_value_list_get(&list, 1)->data.i == 2);
    tc_value_free(&list);

    tc_value dict = tc_value_dict_new();
    tc_value_dict_set(&dict, "name", tc_value_string("test"));
    tc_value_dict_set(&dict, "value", tc_value_int(123));
    GUARD_C_CHECK(tc_value_dict_has(&dict, "name"));
    GUARD_C_CHECK(tc_value_dict_get(&dict, "value")->data.i == 123);
    GUARD_C_CHECK_EQ_SIZE(2, tc_value_dict_size(&dict));
    tc_value_free(&dict);

    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_tc_dlist);
    GUARD_C_RUN(test_tc_value);
    return GUARD_C_END();
}
