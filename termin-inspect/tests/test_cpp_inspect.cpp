#include "tc_inspect_cpp.hpp"
#include "inspect/tc_runtime_type_registry.h"

#include <any>
#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

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

struct RuntimeInstanceProbe {
    tc_runtime_type_instance_link link;
    int value = 0;
};

static int g_destroyed_runtime_instance_probe_facets = 0;

void destroy_runtime_instance_probe_facet(void* payload) {
    delete static_cast<int*>(payload);
    g_destroyed_runtime_instance_probe_facets++;
}

bool collect_runtime_instance_probe(void* instance, void* user_data) {
    auto* values = static_cast<std::vector<int>*>(user_data);
    auto* probe = static_cast<RuntimeInstanceProbe*>(instance);
    values->push_back(probe ? probe->value : -1);
    return true;
}

void expect_near(float a, float b, float eps = 1e-6f) {
    CHECK(std::fabs(a - b) <= eps);
}

} // namespace

TEST_CASE("C++ kind serialization mismatch is logged and returns nil") {
    tc::init_cpp_inspect_vtable();
    tc::register_builtin_cpp_kinds();

    tc_value value = tc::KindRegistryCpp::instance().serialize(
        "int",
        std::any(std::string("not-an-int")));

    CHECK(value.type == TC_VALUE_NIL);
    tc_value_free(&value);
}

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

TEST_CASE("InspectRegistry stores type owner and parent in runtime type records") {
    tc::init_cpp_inspect_vtable();
    tc::register_builtin_cpp_kinds();

    auto& inspect = tc::InspectRegistry::instance();

    inspect.unregister_type("RuntimeTypeBaseProbe");
    inspect.unregister_type("RuntimeTypeDerivedProbe");
    tc_runtime_type_registry_unregister_type("RuntimeTypeBaseProbe");
    tc_runtime_type_registry_unregister_type("RuntimeTypeDerivedProbe");

    inspect.set_registration_owner("runtime_type_probe_module");
    inspect.add<CppBaseComponent, int>(
        "RuntimeTypeBaseProbe",
        &CppBaseComponent::hp,
        "hp",
        "HP",
        "int"
    );
    inspect.add<CppDerivedComponent, std::string>(
        "RuntimeTypeDerivedProbe",
        &CppDerivedComponent::title,
        "title",
        "Title",
        "string"
    );
    inspect.set_type_parent("RuntimeTypeDerivedProbe", "RuntimeTypeBaseProbe");
    inspect.set_registration_owner("");

    CHECK(tc_runtime_type_registry_has_type("RuntimeTypeBaseProbe"));
    CHECK(tc_runtime_type_registry_has_type("RuntimeTypeDerivedProbe"));
    CHECK_EQ(std::string(tc_runtime_type_registry_get_owner("RuntimeTypeBaseProbe")), std::string("runtime_type_probe_module"));
    CHECK_EQ(std::string(tc_runtime_type_registry_get_owner("RuntimeTypeDerivedProbe")), std::string("runtime_type_probe_module"));
    CHECK_EQ(std::string(tc_runtime_type_registry_get_parent("RuntimeTypeDerivedProbe")), std::string("RuntimeTypeBaseProbe"));
    CHECK_EQ(inspect.owner_of("RuntimeTypeDerivedProbe"), std::string("runtime_type_probe_module"));
    CHECK_EQ(inspect.get_type_parent("RuntimeTypeDerivedProbe"), std::string("RuntimeTypeBaseProbe"));
    CHECK(inspect.find_field("RuntimeTypeDerivedProbe", "hp") != nullptr);

    CHECK_EQ(tc_runtime_type_registry_unregister_owner("runtime_type_probe_module"), 2u);
    CHECK(!tc_runtime_type_registry_has_type("RuntimeTypeBaseProbe"));
    CHECK(!tc_runtime_type_registry_has_type("RuntimeTypeDerivedProbe"));
    CHECK(!inspect.has_type("RuntimeTypeBaseProbe"));
    CHECK(!inspect.has_type("RuntimeTypeDerivedProbe"));
}

TEST_CASE("Runtime type records keep tombstones while live instances are linked") {
    const char* type_name = "RuntimeTypeInstanceProbe";
    tc_runtime_type_registry_unregister_type(type_name);

    RuntimeInstanceProbe first;
    RuntimeInstanceProbe second;
    tc_runtime_type_instance_link_init(&first.link);
    tc_runtime_type_instance_link_init(&second.link);
    first.value = 11;
    second.value = 29;

    CHECK(tc_runtime_type_registry_ensure_type(type_name));
    CHECK(tc_runtime_type_registry_link_instance(type_name, &first.link, &first));
    CHECK(tc_runtime_type_registry_link_instance(type_name, &second.link, &second));
    CHECK_EQ(tc_runtime_type_registry_instance_count(type_name), 2u);
    CHECK(tc_runtime_type_registry_instance_is_current(&first.link));

    std::vector<int> values;
    tc_runtime_type_registry_foreach_instance(
        type_name,
        collect_runtime_instance_probe,
        &values
    );
    REQUIRE_EQ(values.size(), 2u);
    CHECK_EQ(values[0], 11);
    CHECK_EQ(values[1], 29);

    tc_runtime_type_registry_unregister_type(type_name);
    CHECK(!tc_runtime_type_registry_has_type(type_name));
    CHECK_EQ(tc_runtime_type_registry_instance_count(type_name), 2u);
    CHECK(!tc_runtime_type_registry_instance_is_current(&first.link));

    tc_runtime_type_record_info info;
    REQUIRE(tc_runtime_type_registry_get_info(type_name, &info));
    CHECK(info.tombstoned);
    CHECK_EQ(info.facet_count, 0u);
    CHECK_EQ(info.instance_count, 2u);

    tc_runtime_type_registry_unlink_instance(&first.link);
    REQUIRE(tc_runtime_type_registry_get_info(type_name, &info));
    CHECK(info.tombstoned);
    CHECK_EQ(info.instance_count, 1u);

    tc_runtime_type_registry_unlink_instance(&second.link);
    CHECK(!tc_runtime_type_registry_get_info(type_name, &info));
    CHECK_EQ(tc_runtime_type_registry_instance_count(type_name), 0u);
}

TEST_CASE("Owner cleanup removes facets but keeps live instance tombstones") {
    const char* type_name = "RuntimeTypeOwnedInstanceProbe";
    const char* owner = "runtime_type_instance_probe_module";
    tc_runtime_type_registry_unregister_type(type_name);
    g_destroyed_runtime_instance_probe_facets = 0;

    RuntimeInstanceProbe probe;
    tc_runtime_type_instance_link_init(&probe.link);
    probe.value = 71;

    tc_runtime_type_registry_set_registration_owner(owner);
    CHECK(tc_runtime_type_registry_ensure_type(type_name));
    tc_runtime_type_registry_set_registration_owner("");
    CHECK(tc_runtime_type_registry_set_facet(
        type_name,
        "termin.test.instance_probe",
        new int(5),
        destroy_runtime_instance_probe_facet,
        1
    ));
    CHECK(tc_runtime_type_registry_link_instance(type_name, &probe.link, &probe));

    CHECK_EQ(tc_runtime_type_registry_unregister_owner(owner), 1u);
    CHECK_EQ(g_destroyed_runtime_instance_probe_facets, 1);
    CHECK(!tc_runtime_type_registry_has_type(type_name));

    tc_runtime_type_record_info info;
    REQUIRE(tc_runtime_type_registry_get_info(type_name, &info));
    CHECK(info.tombstoned);
    CHECK_EQ(info.facet_count, 0u);
    CHECK_EQ(info.instance_count, 1u);
    CHECK_EQ(tc_runtime_type_registry_unregister_owner(owner), 0u);

    tc_runtime_type_registry_unlink_instance(&probe.link);
    CHECK(!tc_runtime_type_registry_get_info(type_name, &info));
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
