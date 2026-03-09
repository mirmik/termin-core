#include "tc_inspect_cpp.hpp"

#include <cassert>
#include <cmath>
#include <string>

namespace {

struct CppBaseComponent {
    int hp = 100;
    float speed = 2.5f;
};

struct CppDerivedComponent : public CppBaseComponent {
    std::string title = "rookie";
};

void expect_near(float a, float b, float eps = 1e-6f) {
    assert(std::fabs(a - b) <= eps);
}

} // namespace

int main() {
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

    assert(reg.all_fields_count("CppDerivedComponent") == 3);
    assert(reg.find_field("CppDerivedComponent", "hp") != nullptr);
    assert(reg.find_field("CppDerivedComponent", "speed") != nullptr);
    assert(reg.find_field("CppDerivedComponent", "title") != nullptr);

    tc_value hp = reg.get_tc_value(&obj, "CppDerivedComponent", "hp");
    assert(hp.type == TC_VALUE_INT);
    assert(hp.data.i == 100);
    tc_value_free(&hp);

    tc_value speed = reg.get_tc_value(&obj, "CppDerivedComponent", "speed");
    assert(speed.type == TC_VALUE_FLOAT);
    expect_near(speed.data.f, 2.5f);
    tc_value_free(&speed);

    tc_value new_hp = tc_value_int(1337);
    reg.set_tc_value(&obj, "CppDerivedComponent", "hp", new_hp, nullptr);
    tc_value_free(&new_hp);
    assert(obj.hp == 1337);

    tc_value serialized = reg.serialize_all(&obj, "CppDerivedComponent");
    assert(serialized.type == TC_VALUE_DICT);

    tc_value* hp_field = tc_value_dict_get(&serialized, "hp");
    assert(hp_field && hp_field->type == TC_VALUE_INT && hp_field->data.i == 1337);
    tc_value* speed_field = tc_value_dict_get(&serialized, "speed");
    assert(speed_field && speed_field->type == TC_VALUE_FLOAT);
    tc_value* title_field = tc_value_dict_get(&serialized, "title");
    assert(title_field && title_field->type == TC_VALUE_STRING);
    assert(std::string(title_field->data.s) == "rookie");

    tc_value input = tc_value_dict_new();
    tc_value_dict_set(&input, "hp", tc_value_int(7));
    tc_value_dict_set(&input, "speed", tc_value_float(9.0f));
    tc_value_dict_set(&input, "title", tc_value_string("veteran"));

    reg.deserialize_all(&obj, "CppDerivedComponent", &input, nullptr);
    assert(obj.hp == 7);
    expect_near(obj.speed, 9.0f);
    assert(obj.title == "veteran");

    tc_value_free(&input);
    tc_value_free(&serialized);

    return 0;
}
