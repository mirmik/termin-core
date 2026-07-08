#include <string>
#include <type_traits>

#include <tcbase/tc_value.hpp>

#include "guard_main.h"

TEST_CASE("tc Value owns and releases raw tc_value") {
    tc::Value root = tc::Value::dict();
    root.set("name", tc::Value::string("root"));
    root.set("count", tc::Value::integer(2));

    CHECK(root.view().is_dict());
    CHECK(root.view().dict_get("name").as_string() == "root");
    CHECK(root.view().dict_get("count").as_int() == 2);

    tc_value raw = root.release();
    CHECK(root.is_nil());
    CHECK(raw.type == TC_VALUE_DICT);
    CHECK(tc_value_dict_size(&raw) == 2);
    tc_value_free(&raw);
}

TEST_CASE("tc Value copy is deep and independent") {
    tc::Value original = tc::Value::dict();
    original.set("name", tc::Value::string("original"));

    tc::Value list = tc::Value::list();
    list.push(tc::Value::integer(1));
    list.push(tc::Value::integer(2));
    original.set("items", std::move(list));

    tc::Value copy = original;
    copy.set("name", tc::Value::string("copy"));
    tc_value_list_push(
        tc_value_dict_get(copy.raw(), "items"),
        tc_value_int(3)
    );

    CHECK(original.view().dict_get("name").as_string() == "original");
    CHECK(copy.view().dict_get("name").as_string() == "copy");
    CHECK(original.view().dict_get("items").size() == 2);
    CHECK(copy.view().dict_get("items").size() == 3);
}

TEST_CASE("tc Value move transfers ownership and nils source") {
    tc::Value source = tc::Value::string("payload");
    tc::Value moved = std::move(source);

    CHECK(source.is_nil());
    CHECK(moved.view().as_string() == "payload");

    tc::Value assigned;
    assigned = std::move(moved);

    CHECK(moved.is_nil());
    CHECK(assigned.view().as_string() == "payload");
}

TEST_CASE("tc Value copy_of duplicates borrowed raw value") {
    tc_value raw = tc_value_string("borrowed");
    tc::Value copy = tc::Value::copy_of(raw);

    raw.data.s[0] = 'B';

    CHECK(std::string(raw.data.s) == "Borrowed");
    CHECK(copy.view().as_string() == "borrowed");

    tc_value_free(&raw);
}

TEST_CASE("tc ValueView reads lists and dicts without ownership") {
    static_assert(std::is_copy_constructible_v<tc::Value>);
    static_assert(std::is_move_constructible_v<tc::Value>);

    tc::Value list = tc::Value::list();
    list.push(tc::Value::integer(10));
    list.push(tc::Value::number(2.5));

    tc::Value root = tc::Value::dict();
    root.set("enabled", tc::Value::boolean(true));
    root.set("values", std::move(list));

    tc::ValueView view = root.view();
    tc::ValueView values = view.dict_get("values");

    CHECK(view.dict_get("enabled").as_bool());
    CHECK(values.size() == 2);
    CHECK(values.list_at(0).as_int() == 10);
    CHECK(values.list_at(1).as_number() == 2.5);
    CHECK_FALSE(values.list_at(10));
    CHECK_FALSE(view.dict_get("missing"));
}

GUARD_TEST_MAIN();
