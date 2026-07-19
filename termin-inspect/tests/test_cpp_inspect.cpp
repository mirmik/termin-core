#include "tc_inspect_cpp.hpp"
#include "inspect/tc_runtime_type_registry.h"

#include <algorithm>
#include <any>
#include <cmath>
#include <cstdint>
#include <limits>
#include <optional>
#include <stdexcept>
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

struct CppUnsignedComponent {
    unsigned int stable_id = 0;
};

struct CheckedSetterComponent {
    int value = 3;
    std::optional<int> nullable = 7;
};

static std::vector<std::string> g_inspect_logs;

void capture_inspect_log(tc_log_level, const char* message) {
    g_inspect_logs.emplace_back(message ? message : "");
}

struct RuntimeInstanceProbe {
    tc_runtime_type_instance_link link;
    int value = 0;
};

static int g_destroyed_runtime_instance_probe_facets = 0;
static int g_prepared_runtime_instance_probe_facets = 0;

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

bool prepare_runtime_instance_probe_facet(
    const char* type_name,
    void* payload,
    void* context
) {
    auto* marker = static_cast<int*>(payload);
    auto* context_marker = static_cast<int*>(context);
    if (!type_name || std::string(type_name) != "RuntimeTypePrepareProbe") {
        return false;
    }
    if (!marker || !context_marker) {
        return false;
    }
    *marker += *context_marker;
    g_prepared_runtime_instance_probe_facets++;
    return true;
}

bool refuse_runtime_instance_probe_facet(
    const char*,
    void*,
    void*
) {
    g_prepared_runtime_instance_probe_facets++;
    return false;
}

bool accept_runtime_instance_probe_facet(const char*, void*, void*) {
    g_prepared_runtime_instance_probe_facets++;
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

TEST_CASE("C++ uint32 kind roundtrips the full unsigned int range") {
    tc::init_cpp_inspect_vtable();
    tc::register_builtin_cpp_kinds();

    auto& reg = tc::InspectRegistry::instance();
    reg.unregister_type("CppUnsignedComponent");
    reg.add<CppUnsignedComponent, unsigned int>(
        "CppUnsignedComponent",
        &CppUnsignedComponent::stable_id,
        "stable_id",
        "Stable Id",
        "uint32",
        0.0,
        static_cast<double>(std::numeric_limits<unsigned int>::max()),
        1.0
    );

    CppUnsignedComponent object;
    object.stable_id = 4000000000u;
    tc_value serialized = reg.serialize_all(&object, "CppUnsignedComponent");
    REQUIRE(serialized.type == TC_VALUE_DICT);
    tc_value* stable_id = tc_value_dict_get(&serialized, "stable_id");
    REQUIRE(stable_id != nullptr);
    CHECK_EQ(stable_id->type, TC_VALUE_INT);
    CHECK_EQ(stable_id->data.i, 4000000000LL);

    object.stable_id = 0;
    reg.deserialize_all(&object, "CppUnsignedComponent", &serialized, nullptr);
    CHECK_EQ(object.stable_id, 4000000000u);
    tc_value_free(&serialized);
}

TEST_CASE("C++ field serialization mismatch logs the registered type and path") {
    tc::init_cpp_inspect_vtable();
    tc::register_builtin_cpp_kinds();

    auto& reg = tc::InspectRegistry::instance();
    reg.unregister_type("CppUnsignedMismatch");
    reg.add<CppUnsignedComponent, unsigned int>(
        "CppUnsignedMismatch",
        &CppUnsignedComponent::stable_id,
        "stable_id",
        "Stable Id",
        "int"
    );

    g_inspect_logs.clear();
    tc_log_set_callback(capture_inspect_log);
    CppUnsignedComponent object;
    tc_value value = reg.get_tc_value(&object, "CppUnsignedMismatch", "stable_id");
    tc_log_set_callback(nullptr);

    CHECK_EQ(value.type, TC_VALUE_NIL);
    tc_value_free(&value);
    CHECK(std::any_of(
        g_inspect_logs.begin(),
        g_inspect_logs.end(),
        [](const std::string& message) {
            return message.find("CppUnsignedMismatch.stable_id") != std::string::npos;
        }
    ));
}

TEST_CASE("checked C++ setters report conversion, access, and callback failures") {
    tc::init_cpp_inspect_vtable();
    tc::register_builtin_cpp_kinds();

    auto& kinds = tc::KindRegistryCpp::instance();
    kinds.register_kind(
        "optional_int",
        [](const std::any& value) {
            const auto optional = std::any_cast<std::optional<int>>(value);
            return optional ? tc_value_int(*optional) : tc_value_nil();
        },
        [](const tc_value* value, void*) -> std::any {
            if (value->type == TC_VALUE_NIL) {
                return std::optional<int>{};
            }
            return std::optional<int>{tc::tc_value_to_int(value)};
        });

    auto& reg = tc::InspectRegistry::instance();
    reg.unregister_type("CheckedSetterComponent");
    reg.add<CheckedSetterComponent, int>(
        "CheckedSetterComponent", &CheckedSetterComponent::value,
        "value", "Value", "int");
    reg.add<CheckedSetterComponent, std::optional<int>>(
        "CheckedSetterComponent", &CheckedSetterComponent::nullable,
        "nullable", "Nullable", "optional_int");
    reg.add_with_callbacks<CheckedSetterComponent, int>(
        "CheckedSetterComponent", "throwing", "Throwing", "int",
        [](CheckedSetterComponent* object) { return object->value; },
        [](CheckedSetterComponent*, int) { throw std::runtime_error("setter refused value"); });

    tc::InspectFieldInfo read_only;
    read_only.type_name = "CheckedSetterComponent";
    read_only.path = "read_only";
    read_only.kind = "int";
    read_only.getter = [](void* object) {
        return tc_value_int(static_cast<CheckedSetterComponent*>(object)->value);
    };
    reg.add_serializable_field("CheckedSetterComponent", std::move(read_only));

    CheckedSetterComponent object;
    CHECK(tc_inspect_set_checked(
        &object, "CheckedSetterComponent", "value", tc_value_int(11), nullptr));
    CHECK_EQ(object.value, 11);

    tc_value invalid = tc_value_string("not-an-int");
    CHECK(!tc_inspect_set_checked(
        &object, "CheckedSetterComponent", "value", invalid, nullptr));
    tc_value_free(&invalid);
    CHECK_EQ(object.value, 11);

    CHECK(!tc_inspect_set_checked(
        &object, "CheckedSetterComponent", "throwing", tc_value_int(12), nullptr));
    CHECK(!tc_inspect_set_checked(
        &object, "CheckedSetterComponent", "missing", tc_value_int(12), nullptr));
    CHECK(!tc_inspect_set_checked(
        &object, "CheckedSetterComponent", "read_only", tc_value_int(12), nullptr));

    CHECK(tc_inspect_set_checked(
        &object, "CheckedSetterComponent", "nullable", tc_value_nil(), nullptr));
    CHECK(!object.nullable.has_value());

    object.nullable = 21;
    tc_value nullable_payload = tc_value_dict_new();
    tc_value_dict_set(&nullable_payload, "nullable", tc_value_nil());
    const tc_inspect_apply_result nullable_result = tc_inspect_deserialize_checked(
        &object, "CheckedSetterComponent", &nullable_payload, nullptr);
    CHECK_EQ(nullable_result.status, TC_INSPECT_APPLY_OK);
    CHECK_EQ(nullable_result.applied_fields, 1u);
    CHECK(!object.nullable.has_value());
    tc_value_free(&nullable_payload);
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

TEST_CASE("Runtime type facet prepare unload receives context and can refuse cleanup") {
    const char* type_name = "RuntimeTypePrepareProbe";
    const char* owner = "runtime_type_prepare_probe_module";
    tc_runtime_type_registry_unregister_type(type_name);
    g_destroyed_runtime_instance_probe_facets = 0;
    g_prepared_runtime_instance_probe_facets = 0;

    tc_runtime_type_registry_set_registration_owner(owner);
    CHECK(tc_runtime_type_registry_ensure_type(type_name));
    tc_runtime_type_registry_set_registration_owner("");

    CHECK(tc_runtime_type_registry_set_facet_with_lifecycle(
        type_name,
        "termin.test.prepare_probe",
        new int(10),
        destroy_runtime_instance_probe_facet,
        prepare_runtime_instance_probe_facet,
        1
    ));

    int context_marker = 32;
    CHECK_EQ(
        tc_runtime_type_registry_unregister_owner_with_context(owner, &context_marker),
        1u
    );
    CHECK_EQ(g_prepared_runtime_instance_probe_facets, 1);
    CHECK_EQ(g_destroyed_runtime_instance_probe_facets, 1);
    CHECK(!tc_runtime_type_registry_has_type(type_name));

    const char* refusing_type_name = "RuntimeTypePrepareRefuseProbe";
    tc_runtime_type_registry_unregister_type(refusing_type_name);
    tc_runtime_type_registry_set_registration_owner(owner);
    CHECK(tc_runtime_type_registry_ensure_type(refusing_type_name));
    tc_runtime_type_registry_set_registration_owner("");
    CHECK(tc_runtime_type_registry_set_facet_with_lifecycle(
        refusing_type_name,
        "termin.test.prepare_refuse_probe",
        new int(1),
        destroy_runtime_instance_probe_facet,
        refuse_runtime_instance_probe_facet,
        1
    ));

    CHECK_EQ(tc_runtime_type_registry_unregister_owner_with_context(owner, nullptr), 0u);
    CHECK(tc_runtime_type_registry_has_type(refusing_type_name));
    CHECK(tc_runtime_type_registry_remove_facet(
        refusing_type_name,
        "termin.test.prepare_refuse_probe"
    ));
    tc_runtime_type_registry_unregister_type(refusing_type_name);
}

TEST_CASE("Runtime type owner unload prepares every record before atomic commit") {
    const char* owner = "runtime_type_atomic_owner";
    const char* accepted_type = "RuntimeTypeAtomicAccepted";
    const char* refused_type = "RuntimeTypeAtomicRefused";
    tc_runtime_type_registry_unregister_type(accepted_type);
    tc_runtime_type_registry_unregister_type(refused_type);
    g_destroyed_runtime_instance_probe_facets = 0;
    g_prepared_runtime_instance_probe_facets = 0;

    tc_runtime_type_registry_set_registration_owner(owner);
    CHECK(tc_runtime_type_registry_ensure_type(accepted_type));
    CHECK(tc_runtime_type_registry_ensure_type(refused_type));
    tc_runtime_type_registry_set_registration_owner("");
    CHECK(tc_runtime_type_registry_set_facet_with_lifecycle(
        accepted_type,
        "termin.test.atomic_accept",
        new int(1),
        destroy_runtime_instance_probe_facet,
        accept_runtime_instance_probe_facet,
        1
    ));
    CHECK(tc_runtime_type_registry_set_facet_with_lifecycle(
        refused_type,
        "termin.test.atomic_refuse",
        new int(2),
        destroy_runtime_instance_probe_facet,
        refuse_runtime_instance_probe_facet,
        1
    ));

    CHECK(!tc_runtime_type_registry_prepare_owner_unload(owner, nullptr));
    CHECK(tc_runtime_type_registry_has_type(accepted_type));
    CHECK(tc_runtime_type_registry_has_type(refused_type));
    CHECK(tc_runtime_type_registry_has_facet(accepted_type, "termin.test.atomic_accept"));
    CHECK(tc_runtime_type_registry_has_facet(refused_type, "termin.test.atomic_refuse"));
    CHECK_EQ(g_destroyed_runtime_instance_probe_facets, 0);

    CHECK(tc_runtime_type_registry_remove_facet(refused_type, "termin.test.atomic_refuse"));
    CHECK(tc_runtime_type_registry_prepare_owner_unload(owner, nullptr));
    size_t removed = 0;
    CHECK(tc_runtime_type_registry_commit_owner_unload(owner, &removed));
    CHECK_EQ(removed, 1u);
    CHECK(!tc_runtime_type_registry_has_type(accepted_type));
    CHECK(!tc_runtime_type_registry_has_type(refused_type));
    CHECK_EQ(g_destroyed_runtime_instance_probe_facets, 2);
}

TEST_CASE("Runtime type descriptor rejects partial and duplicate facets atomically") {
    const char* type_name = "RuntimeTypeDescriptorPartial";
    tc_runtime_type_registry_unregister_type(type_name);
    g_destroyed_runtime_instance_probe_facets = 0;

    auto* descriptor = tc_runtime_type_descriptor_create(type_name, "descriptor_owner", nullptr);
    REQUIRE(descriptor != nullptr);
    CHECK(tc_runtime_type_descriptor_add_facet(
        descriptor,
        "termin.test.descriptor",
        new int(1),
        destroy_runtime_instance_probe_facet,
        nullptr,
        1
    ));
    CHECK(!tc_runtime_type_descriptor_add_facet(
        descriptor,
        "termin.test.descriptor",
        new int(2),
        destroy_runtime_instance_probe_facet,
        nullptr,
        1
    ));
    CHECK_EQ(g_destroyed_runtime_instance_probe_facets, 1);
    CHECK(!tc_runtime_type_registry_commit_descriptor(descriptor));
    CHECK_EQ(g_destroyed_runtime_instance_probe_facets, 2);
    CHECK(!tc_runtime_type_registry_has_type(type_name));
    CHECK(tc_runtime_type_registry_get_owner(type_name) == nullptr);

    const char* invalid_abi_type = "RuntimeTypeDescriptorInvalidAbi";
    tc_runtime_type_registry_unregister_type(invalid_abi_type);
    auto* invalid_abi = tc_runtime_type_descriptor_create(
        invalid_abi_type,
        "descriptor_owner",
        nullptr
    );
    REQUIRE(invalid_abi != nullptr);
    CHECK(!tc_runtime_type_descriptor_add_facet(
        invalid_abi,
        "termin.test.invalid_abi",
        new int(8),
        destroy_runtime_instance_probe_facet,
        nullptr,
        0
    ));
    CHECK(!tc_runtime_type_registry_commit_descriptor(invalid_abi));
    CHECK_EQ(g_destroyed_runtime_instance_probe_facets, 3);
    CHECK(!tc_runtime_type_registry_has_type(invalid_abi_type));
}

TEST_CASE("Runtime type descriptor validation leaves no missing-parent shell") {
    const char* type_name = "RuntimeTypeDescriptorMissingParent";
    tc_runtime_type_registry_unregister_type(type_name);
    g_destroyed_runtime_instance_probe_facets = 0;

    auto* descriptor = tc_runtime_type_descriptor_create(
        type_name,
        "descriptor_owner",
        "RuntimeTypeDescriptorAbsentParent"
    );
    REQUIRE(descriptor != nullptr);
    CHECK(tc_runtime_type_descriptor_add_facet(
        descriptor,
        "termin.test.missing_parent",
        new int(3),
        destroy_runtime_instance_probe_facet,
        nullptr,
        1
    ));
    CHECK(!tc_runtime_type_registry_commit_descriptor(descriptor));
    CHECK_EQ(g_destroyed_runtime_instance_probe_facets, 1);
    tc_runtime_type_record_info info;
    CHECK(!tc_runtime_type_registry_get_info(type_name, &info));
    CHECK(!tc_runtime_type_registry_has_type(type_name));
}

TEST_CASE("Runtime type descriptor rejects active replacement and preserves old callbacks") {
    const char* type_name = "RuntimeTypeDescriptorActive";
    const char* owner = "descriptor_owner";
    tc_runtime_type_registry_unregister_type(type_name);
    g_destroyed_runtime_instance_probe_facets = 0;

    auto* first = tc_runtime_type_descriptor_create(type_name, owner, nullptr);
    REQUIRE(first != nullptr);
    CHECK(tc_runtime_type_descriptor_add_facet(
        first,
        "termin.test.active",
        new int(4),
        destroy_runtime_instance_probe_facet,
        nullptr,
        1
    ));
    CHECK(tc_runtime_type_registry_commit_descriptor(first));
    void* old_payload = tc_runtime_type_registry_get_facet(type_name, "termin.test.active");
    REQUIRE(old_payload != nullptr);

    auto* replacement = tc_runtime_type_descriptor_create(type_name, owner, nullptr);
    REQUIRE(replacement != nullptr);
    CHECK(tc_runtime_type_descriptor_add_facet(
        replacement,
        "termin.test.active",
        new int(5),
        destroy_runtime_instance_probe_facet,
        nullptr,
        1
    ));
    CHECK(!tc_runtime_type_registry_commit_descriptor(replacement));
    CHECK_EQ(g_destroyed_runtime_instance_probe_facets, 1);
    CHECK(tc_runtime_type_registry_get_facet(type_name, "termin.test.active") == old_payload);

    tc_runtime_type_registry_unregister_type(type_name);
    CHECK_EQ(g_destroyed_runtime_instance_probe_facets, 2);
}

TEST_CASE("Runtime type descriptor replaces compatible tombstone and preserves instance index") {
    const char* type_name = "RuntimeTypeDescriptorTombstone";
    const char* owner = "descriptor_owner";
    tc_runtime_type_registry_unregister_type(type_name);
    g_destroyed_runtime_instance_probe_facets = 0;

    auto* first = tc_runtime_type_descriptor_create(type_name, owner, nullptr);
    REQUIRE(first != nullptr);
    CHECK(tc_runtime_type_descriptor_add_facet(
        first,
        "termin.test.old_callback",
        new int(6),
        destroy_runtime_instance_probe_facet,
        nullptr,
        1
    ));
    CHECK(tc_runtime_type_registry_commit_descriptor(first));

    RuntimeInstanceProbe old_instance;
    tc_runtime_type_instance_link_init(&old_instance.link);
    CHECK(tc_runtime_type_registry_link_instance(type_name, &old_instance.link, &old_instance));
    tc_runtime_type_registry_unregister_type(type_name);
    CHECK_EQ(g_destroyed_runtime_instance_probe_facets, 1);
    CHECK(tc_runtime_type_registry_get_facet(type_name, "termin.test.old_callback") == nullptr);
    CHECK(!tc_runtime_type_registry_instance_is_current(&old_instance.link));

    tc_runtime_type_record_info tombstone_info;
    REQUIRE(tc_runtime_type_registry_get_info(type_name, &tombstone_info));
    REQUIRE(tombstone_info.tombstoned);
    uint64_t tombstone_generation = tombstone_info.generation;

    auto* replacement = tc_runtime_type_descriptor_create(type_name, owner, nullptr);
    REQUIRE(replacement != nullptr);
    CHECK(tc_runtime_type_descriptor_add_facet(
        replacement,
        "termin.test.new_callback",
        new int(7),
        destroy_runtime_instance_probe_facet,
        nullptr,
        1
    ));
    CHECK(tc_runtime_type_registry_commit_descriptor(replacement));

    tc_runtime_type_record_info current_info;
    REQUIRE(tc_runtime_type_registry_get_info(type_name, &current_info));
    CHECK(!current_info.tombstoned);
    CHECK_EQ(current_info.generation, tombstone_generation + 1);
    CHECK_EQ(current_info.instance_count, 1u);
    CHECK(!tc_runtime_type_registry_instance_is_current(&old_instance.link));
    CHECK(tc_runtime_type_registry_get_facet(type_name, "termin.test.old_callback") == nullptr);
    CHECK(tc_runtime_type_registry_get_facet(type_name, "termin.test.new_callback") != nullptr);

    RuntimeInstanceProbe new_instance;
    tc_runtime_type_instance_link_init(&new_instance.link);
    CHECK(tc_runtime_type_registry_link_instance(type_name, &new_instance.link, &new_instance));
    CHECK(tc_runtime_type_registry_instance_is_current(&new_instance.link));
    tc_runtime_type_registry_unlink_instance(&old_instance.link);
    tc_runtime_type_registry_unlink_instance(&new_instance.link);
    tc_runtime_type_registry_unregister_type(type_name);
    CHECK_EQ(g_destroyed_runtime_instance_probe_facets, 2);
}

TEST_CASE("Runtime type descriptor rejects cyclic parent and foreign tombstone owner") {
    const char* root_name = "RuntimeTypeDescriptorCycleRoot";
    const char* child_name = "RuntimeTypeDescriptorCycleChild";
    const char* owner = "descriptor_cycle_owner";
    tc_runtime_type_registry_unregister_type(child_name);
    tc_runtime_type_registry_unregister_type(root_name);

    auto* root = tc_runtime_type_descriptor_create(root_name, owner, nullptr);
    REQUIRE(root != nullptr);
    CHECK(tc_runtime_type_registry_commit_descriptor(root));
    auto* child = tc_runtime_type_descriptor_create(child_name, owner, root_name);
    REQUIRE(child != nullptr);
    CHECK(tc_runtime_type_registry_commit_descriptor(child));

    RuntimeInstanceProbe instance;
    tc_runtime_type_instance_link_init(&instance.link);
    CHECK(tc_runtime_type_registry_link_instance(root_name, &instance.link, &instance));
    tc_runtime_type_registry_unregister_type(root_name);

    auto* cyclic = tc_runtime_type_descriptor_create(root_name, owner, child_name);
    REQUIRE(cyclic != nullptr);
    CHECK(!tc_runtime_type_registry_commit_descriptor(cyclic));
    auto* foreign = tc_runtime_type_descriptor_create(root_name, "foreign_owner", nullptr);
    REQUIRE(foreign != nullptr);
    CHECK(!tc_runtime_type_registry_commit_descriptor(foreign));

    tc_runtime_type_record_info info;
    REQUIRE(tc_runtime_type_registry_get_info(root_name, &info));
    CHECK(info.tombstoned);
    CHECK_EQ(std::string(info.owner), std::string(owner));
    tc_runtime_type_registry_unregister_type(child_name);
    tc_runtime_type_registry_unlink_instance(&instance.link);
    CHECK(!tc_runtime_type_registry_get_info(root_name, &info));
}

TEST_CASE("Inspect facet builder validates and publishes callbacks atomically") {
    const char* type_name = "InspectFacetBuilderProbe";
    const char* owner = "inspect_facet_builder_owner";
    tc_runtime_type_registry_unregister_type(type_name);

    std::weak_ptr<int> callback_lifetime;
    {
        auto token = std::make_shared<int>(17);
        callback_lifetime = token;

        tc::InspectFacetBuilder builder(type_name);
        CHECK(builder.set_backend(tc::TypeBackend::Cpp));
        tc_value metadata = tc_value_dict_new();
        tc_value_dict_set(&metadata, "category", tc_value_string("Tests"));
        CHECK(builder.set_metadata(&metadata));
        tc_value_free(&metadata);

        tc::InspectFieldInfo info;
        info.type_name = type_name;
        info.path = "value";
        info.label = "Value";
        info.kind = "int";
        info.getter = [token](void*) { return tc_value_int(*token); };
        info.setter = [](void*, tc_value, void*) { return true; };
        CHECK(builder.add_field(std::move(info)));

        auto* descriptor = tc_runtime_type_descriptor_create(type_name, owner, nullptr);
        REQUIRE(descriptor != nullptr);
        CHECK(builder.attach_to(descriptor));
        CHECK(tc_runtime_type_registry_commit_descriptor(descriptor));
    }

    CHECK(!callback_lifetime.expired());
    auto& inspect = tc::InspectRegistry::instance();
    CHECK_EQ(inspect.all_fields_count(type_name), 1u);
    tc_value metadata = inspect.type_metadata(type_name);
    REQUIRE(metadata.type == TC_VALUE_DICT);
    tc_value* category = tc_value_dict_get(&metadata, "category");
    REQUIRE(category != nullptr);
    CHECK_EQ(std::string(category->data.s), std::string("Tests"));
    tc_value_free(&metadata);

    tc_runtime_type_registry_unregister_type(type_name);
    CHECK(callback_lifetime.expired());

    const char* rejected_type = "InspectFacetBuilderRejected";
    tc_runtime_type_registry_unregister_type(rejected_type);
    tc::InspectFacetBuilder duplicate(rejected_type);
    tc::InspectFieldInfo first;
    first.path = "duplicate";
    first.kind = "int";
    first.getter = [](void*) { return tc_value_int(1); };
    CHECK(duplicate.add_field(std::move(first)));
    tc::InspectFieldInfo second;
    second.path = "duplicate";
    second.kind = "int";
    second.getter = [](void*) { return tc_value_int(2); };
    CHECK(!duplicate.add_field(std::move(second)));
    auto* rejected = tc_runtime_type_descriptor_create(rejected_type, owner, nullptr);
    REQUIRE(rejected != nullptr);
    CHECK(!duplicate.attach_to(rejected));
    tc_runtime_type_descriptor_destroy(rejected);
    CHECK(!tc_runtime_type_registry_has_type(rejected_type));

    tc::InspectFacetBuilder invalid_backend("InspectFacetBuilderInvalidBackend");
    CHECK(!invalid_backend.set_backend(static_cast<tc::TypeBackend>(99)));
    tc::InspectFacetBuilder invalid_metadata("InspectFacetBuilderInvalidMetadata");
    tc_value scalar_metadata = tc_value_int(5);
    CHECK(!invalid_metadata.set_metadata(&scalar_metadata));
}

TEST_CASE("Incremental runtime type parent mutation rejects cycles atomically") {
    const char* root_name = "RuntimeTypeParentCycleRoot";
    const char* middle_name = "RuntimeTypeParentCycleMiddle";
    const char* leaf_name = "RuntimeTypeParentCycleLeaf";
    const char* tail_name = "RuntimeTypeParentCycleTail";
    tc_runtime_type_registry_unregister_type(tail_name);
    tc_runtime_type_registry_unregister_type(leaf_name);
    tc_runtime_type_registry_unregister_type(middle_name);
    tc_runtime_type_registry_unregister_type(root_name);

    CHECK(!tc_runtime_type_registry_set_parent(root_name, root_name));
    CHECK(!tc_runtime_type_registry_has_type(root_name));

    CHECK(tc_runtime_type_registry_set_parent(root_name, nullptr));
    CHECK(tc_runtime_type_registry_set_parent(middle_name, root_name));
    CHECK(tc_runtime_type_registry_set_parent(leaf_name, middle_name));
    CHECK(tc_runtime_type_registry_set_parent(tail_name, leaf_name));

    tc_runtime_type_record_info root_before;
    REQUIRE(tc_runtime_type_registry_get_info(root_name, &root_before));
    CHECK(!tc_runtime_type_registry_set_parent(root_name, leaf_name));

    tc_runtime_type_record_info root_after;
    REQUIRE(tc_runtime_type_registry_get_info(root_name, &root_after));
    CHECK_EQ(root_after.generation, root_before.generation);
    CHECK(root_after.parent == nullptr);
    CHECK_EQ(std::string(tc_runtime_type_registry_get_parent(middle_name)), std::string(root_name));
    CHECK_EQ(std::string(tc_runtime_type_registry_get_parent(leaf_name)), std::string(middle_name));
    CHECK_EQ(std::string(tc_runtime_type_registry_get_parent(tail_name)), std::string(leaf_name));

    CHECK(tc_runtime_type_registry_set_parent(leaf_name, nullptr));
    CHECK(tc_runtime_type_registry_get_parent(leaf_name) == nullptr);
    CHECK(tc_runtime_type_registry_set_parent(root_name, tail_name));

    auto& inspect = tc::InspectRegistry::instance();
    CHECK_EQ(inspect.all_fields_count(root_name), 0u);
    CHECK_EQ(inspect.all_fields_count(tail_name), 0u);

    tc_runtime_type_registry_unregister_type(root_name);
    tc_runtime_type_registry_unregister_type(tail_name);
    tc_runtime_type_registry_unregister_type(leaf_name);
    tc_runtime_type_registry_unregister_type(middle_name);
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
        tc::InspectFieldSpec{"CppChoiceComponent", "accessor_mode", "Accessor Mode", "enum"},
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
