#include "tc_inspect_cpp.hpp"

#include <cmath>
#include <string>

#include "guard_main.h"

namespace {

struct CppBaseComponent {
    int hp = 100;
    float speed = 2.5f;
};

struct CppDerivedComponent : public CppBaseComponent {
    std::string title = "rookie";
};

struct CppChoiceComponent {
    int numeric_mode = 1;
    int accessor_mode = 0;
    std::string string_mode = "average";
};

void expect_near(float a, float b, float eps = 1e-6f) {
    CHECK(std::fabs(a - b) <= eps);
}

} // namespace

TEST_CASE("C++ inspect registry roundtrips inherited fields") {
    tc::init_cpp_inspect_vtable();
    (void)tc::KindRegistryCpp::instance();
    tc::register_builtin_cpp_kinds();

    auto& reg = tc::InspectRegistry::instance();
    reg.unregister_type("CppBaseComponent");
    reg.unregister_type("CppDerivedComponent");

    reg.add<CppBaseComponent, int>("CppBaseComponent", &CppBaseComponent::hp, "hp", "HP", "int");
    reg.add<CppBaseComponent, float>("CppBaseComponent", &CppBaseComponent::speed, "speed", "Speed", "float");
    reg.add<CppDerivedComponent, std::string>("CppDerivedComponent", &CppDerivedComponent::title, "title", "Title", "string");
    reg.set_type_parent("CppDerivedComponent", "CppBaseComponent");

    CppDerivedComponent obj;

    CHECK_EQ(reg.all_fields_count("CppDerivedComponent"), 3u);
    CHECK(reg.find_field("CppDerivedComponent", "hp") != nullptr);
    CHECK(reg.find_field("CppDerivedComponent", "speed") != nullptr);
    CHECK(reg.find_field("CppDerivedComponent", "title") != nullptr);

    tc_value hp = reg.get_tc_value(&obj, "CppDerivedComponent", "hp");
    CHECK(hp.type == TC_VALUE_INT);
    CHECK_EQ(hp.data.i, 100);
    tc_value_free(&hp);

    tc_value speed = reg.get_tc_value(&obj, "CppDerivedComponent", "speed");
    CHECK(speed.type == TC_VALUE_FLOAT);
    expect_near(speed.data.f, 2.5f);
    tc_value_free(&speed);

    tc_value new_hp = tc_value_int(1337);
    reg.set_tc_value(&obj, "CppDerivedComponent", "hp", new_hp, nullptr);
    tc_value_free(&new_hp);
    CHECK_EQ(obj.hp, 1337);

    tc_value serialized = reg.serialize_all(&obj, "CppDerivedComponent");
    REQUIRE(serialized.type == TC_VALUE_DICT);

    tc_value* hp_field = tc_value_dict_get(&serialized, "hp");
    CHECK(hp_field && hp_field->type == TC_VALUE_INT && hp_field->data.i == 1337);
    tc_value* speed_field = tc_value_dict_get(&serialized, "speed");
    CHECK(speed_field && speed_field->type == TC_VALUE_FLOAT);
    tc_value* title_field = tc_value_dict_get(&serialized, "title");
    REQUIRE(title_field && title_field->type == TC_VALUE_STRING);
    CHECK_EQ(std::string(title_field->data.s), std::string("rookie"));

    tc_value input = tc_value_dict_new();
    tc_value_dict_set(&input, "hp", tc_value_int(7));
    tc_value_dict_set(&input, "speed", tc_value_float(9.0f));
    tc_value_dict_set(&input, "title", tc_value_string("veteran"));

    reg.deserialize_all(&obj, "CppDerivedComponent", &input, nullptr);
    CHECK_EQ(obj.hp, 7);
    expect_near(obj.speed, 9.0f);
    CHECK_EQ(obj.title, std::string("veteran"));

    tc_value_free(&input);
    tc_value_free(&serialized);
}

TEST_CASE("C++ inspect choices support string enum fields") {
    tc::init_cpp_inspect_vtable();
    (void)tc::KindRegistryCpp::instance();
    tc::register_builtin_cpp_kinds();

    auto& reg = tc::InspectRegistry::instance();
    reg.unregister_type("CppChoiceComponent");

    tc::InspectFieldChoicesRegistrar<CppChoiceComponent, int> numeric_reg{
        &CppChoiceComponent::numeric_mode,
        "CppChoiceComponent",
        "numeric_mode",
        "Numeric Mode",
        "enum",
        {{"0", "Zero"}, {"1", "One"}},
    };
    tc::InspectFieldChoicesRegistrar<CppChoiceComponent, std::string> string_reg{
        &CppChoiceComponent::string_mode,
        "CppChoiceComponent",
        "string_mode",
        "String Mode",
        "enum",
        {{"average", "Average"}, {"min", "Min"}, {"max", "Max"}},
    };
    tc::InspectAccessorFieldChoicesRegistrar<CppChoiceComponent, int> accessor_reg{
        "CppChoiceComponent",
        "accessor_mode",
        "Accessor Mode",
        "enum",
        [](CppChoiceComponent* self) -> int { return self->accessor_mode; },
        [](CppChoiceComponent* self, int value) { self->accessor_mode = value; },
        {{"0", "Zero"}, {"2", "Two"}},
    };

    CppChoiceComponent obj;

    tc_value numeric_value = reg.get_tc_value(&obj, "CppChoiceComponent", "numeric_mode");
    CHECK(numeric_value.type == TC_VALUE_INT);
    CHECK_EQ(numeric_value.data.i, 1);
    tc_value_free(&numeric_value);

    tc_value string_value = reg.get_tc_value(&obj, "CppChoiceComponent", "string_mode");
    REQUIRE(string_value.type == TC_VALUE_STRING);
    CHECK_EQ(std::string(string_value.data.s), std::string("average"));
    tc_value_free(&string_value);

    const auto* accessor_field = reg.find_field("CppChoiceComponent", "accessor_mode");
    REQUIRE(accessor_field != nullptr);
    REQUIRE(accessor_field->choices.size() == 2u);
    CHECK_EQ(accessor_field->choices[1].value, std::string("2"));
    CHECK_EQ(accessor_field->choices[1].label, std::string("Two"));

    tc_value input = tc_value_dict_new();
    tc_value_dict_set(&input, "numeric_mode", tc_value_int(0));
    tc_value_dict_set(&input, "accessor_mode", tc_value_string("2"));
    tc_value_dict_set(&input, "string_mode", tc_value_string("max"));
    reg.deserialize_all(&obj, "CppChoiceComponent", &input, nullptr);

    CHECK_EQ(obj.numeric_mode, 0);
    CHECK_EQ(obj.accessor_mode, 2);
    CHECK_EQ(obj.string_mode, std::string("max"));

    tc_value_free(&input);
}

GUARD_TEST_MAIN();
