#include <string>
#include <type_traits>

#include <tcbase/tc_trent_json.hpp>
#include <tcbase/tc_trent_yaml.hpp>
#include <tcbase/tc_trent.hpp>

#include "guard_main.h"

TEST_CASE("tc trent owns and releases raw tc_value") {
    tc::trent root = tc::trent::dict();
    root.set("name", tc::trent::string("root"));
    root.set("count", tc::trent::integer(2));

    CHECK(root.view().is_dict());
    CHECK(root.view().dict_get("name").as_string() == "root");
    CHECK(root.view().dict_get("count").as_integer() == 2);

    tc_value raw = root.release();
    CHECK(root.is_nil());
    CHECK(raw.type == TC_VALUE_DICT);
    CHECK(tc_value_dict_size(&raw) == 2);
    tc_value_free(&raw);
}

TEST_CASE("tc trent copy is deep and independent") {
    tc::trent original = tc::trent::dict();
    original.set("name", tc::trent::string("original"));

    tc::trent list = tc::trent::list();
    list.push_back(tc::trent::integer(1));
    list.push_back(tc::trent::integer(2));
    original.set("items", std::move(list));

    tc::trent copy = original;
    copy.set("name", tc::trent::string("copy"));
    tc_value_list_push(
        tc_value_dict_get(copy.raw(), "items"),
        tc_value_int(3)
    );

    CHECK(original.view().dict_get("name").as_string() == "original");
    CHECK(copy.view().dict_get("name").as_string() == "copy");
    CHECK(original.view().dict_get("items").size() == 2);
    CHECK(copy.view().dict_get("items").size() == 3);
}

TEST_CASE("tc trent move transfers ownership and nils source") {
    tc::trent source = tc::trent::string("payload");
    tc::trent moved = std::move(source);

    CHECK(source.is_nil());
    CHECK(moved.view().as_string() == "payload");

    tc::trent assigned;
    assigned = std::move(moved);

    CHECK(moved.is_nil());
    CHECK(assigned.view().as_string() == "payload");
}

TEST_CASE("tc trent copy_of duplicates borrowed raw value") {
    tc_value raw = tc_value_string("borrowed");
    tc::trent copy = tc::trent::copy_of(raw);

    raw.data.s[0] = 'B';

    CHECK(std::string(raw.data.s) == "Borrowed");
    CHECK(copy.view().as_string() == "borrowed");

    tc_value_free(&raw);
}

TEST_CASE("tc trent_view reads lists and dicts without ownership") {
    static_assert(std::is_copy_constructible_v<tc::trent>);
    static_assert(std::is_move_constructible_v<tc::trent>);

    tc::trent list = tc::trent::list();
    list.push_back(tc::trent::integer(10));
    list.push_back(tc::trent::numer(2.5));

    tc::trent root = tc::trent::dict();
    root.set("enabled", tc::trent::boolean(true));
    root.set("values", std::move(list));

    tc::trent_view view = root.view();
    tc::trent_view values = view.dict_get("values");

    CHECK(view.dict_get("enabled").as_bool());
    CHECK(values.size() == 2);
    CHECK(values.list_at(0).as_integer() == 10);
    CHECK(values.list_at(1).as_numer() == 2.5);
    CHECK_FALSE(values.list_at(10));
    CHECK_FALSE(view.dict_get("missing"));
}

TEST_CASE("tc trent supports tree mutation syntax") {
    tc::trent data;
    data["entity"]["name"] = "root";
    data["entity"]["enabled"] = true;
    data["entity"]["children"].init(tc::trent_type::list);
    data["entity"]["children"].push_back("child-a");
    data["entity"]["children"].push_back("child-b");

    CHECK(data.is_dict());
    CHECK(data["entity"]["name"].as_string() == "root");
    CHECK(data["entity"]["enabled"].as_bool());
    CHECK(data["entity"]["children"].is_list());
    CHECK(data["entity"]["children"][1].as_string() == "child-b");
}

TEST_CASE("tc trent list and dict ranges expose borrowed views") {
    tc::trent root = tc::trent::dict();
    root["numbers"].init(tc::trent_type::list);
    root["numbers"].push_back(1);
    root["numbers"].push_back(2);
    root["flag"] = true;

    int sum = 0;
    for (tc::trent_view item : root["numbers"].as_list()) {
        sum += static_cast<int>(item.as_integer());
    }
    CHECK(sum == 3);

    bool saw_numbers = false;
    bool saw_flag = false;
    for (auto entry : root.as_dict()) {
        if (std::string(entry.key) == "numbers") {
            saw_numbers = entry.view().is_list();
        }
        if (std::string(entry.key) == "flag") {
            saw_flag = entry.view().as_bool();
        }
    }
    CHECK(saw_numbers);
    CHECK(saw_flag);
}

TEST_CASE("tc trent json facade parses and dumps tree data") {
    tc::trent data = tc::json::parse(R"({"name":"root","values":[1,2],"enabled":true})");

    CHECK(data["name"].as_string() == "root");
    CHECK(data["values"].is_list());
    CHECK(data["values"][0].as_integer() == 1);
    CHECK(data["enabled"].as_bool());

    const std::string dumped = tc::json::dump(data);
    tc::trent reparsed = tc::json::parse(dumped);
    CHECK(reparsed["name"].as_string() == "root");
    CHECK(reparsed["values"][1].as_integer() == 2);
}

TEST_CASE("tc trent yaml facade parses and prints tree data") {
    tc::trent data = tc::yaml::parse(
        "name: root\n"
        "values: [1, 2]\n"
        "enabled: true\n"
    );

    CHECK(data["name"].as_string() == "root");
    CHECK(data["values"][0].as_integer() == 1);
    CHECK(data["enabled"].as_bool());

    const std::string dumped = tc::yaml::to_string(data);
    CHECK(dumped.find("name") != std::string::npos);
    CHECK(dumped.find("root") != std::string::npos);
}

GUARD_TEST_MAIN();
