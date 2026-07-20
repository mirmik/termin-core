#include "inspect/tc_inspect_python.hpp"

#include <Python.h>
#include <nanobind/nanobind.h>

#include <cstdio>
#include <string>

namespace nb = nanobind;

namespace {

bool require_check(bool condition, const char* message) {
    if (!condition) {
        std::fprintf(stderr, "test_python_inspect failed: %s\n", message);
        return false;
    }
    return true;
}

void publish_python_inspect_type(
    const char* type_name,
    const char* parent,
    nb::dict fields,
    bool replace = false
) {
    tc::InspectFacetBuilder inspect = tc::build_python_inspect_facet(
        type_name, std::move(fields));
    auto* descriptor = tc_runtime_type_descriptor_create(
        type_name, "termin-inspect-python-test", parent);
    if (!descriptor) throw std::runtime_error("could not create runtime descriptor");
    if (replace && !tc_runtime_type_descriptor_allow_same_owner_replacement(descriptor)) {
        tc_runtime_type_descriptor_destroy(descriptor);
        throw std::runtime_error("could not enable descriptor replacement");
    }
    if (!inspect.attach_to(descriptor)) {
        tc_runtime_type_descriptor_destroy(descriptor);
        throw std::runtime_error(inspect.error());
    }
    if (!tc_runtime_type_registry_commit_descriptor(descriptor)) {
        throw std::runtime_error("could not commit Python inspect descriptor");
    }
}

} // namespace

int main() {
    tc::init_cpp_inspect_vtable();
    (void)tc::KindRegistryCpp::instance();
    tc::register_builtin_cpp_kinds();

    Py_Initialize();
    tc::init_python_lang_vtable();
    tc::init_python_inspect_vtable();
    {
        auto& reg = tc::InspectRegistry::instance();
        tc_runtime_type_registry_unregister_type("PyBaseComponent");
        tc_runtime_type_registry_unregister_type("PyDerivedComponent");

        const char* script = R"PY(
class InspectField:
    def __init__(self, path=None, label=None, kind="float", min=None, max=None, step=None,
                 action=None, getter=None, setter=None, choices=None,
                 is_serializable=True, is_inspectable=True):
        self.path = path
        self.label = label
        self.kind = kind
        self.min = min
        self.max = max
        self.step = step
        self.action = action
        self.getter = getter
        self.setter = setter
        self.choices = choices
        self.is_serializable = is_serializable
        self.is_inspectable = is_inspectable

class BrokenInspectField:
    path = "broken"
    label = "Broken"
    min = None
    max = None
    step = None
    action = None
    getter = None
    setter = None
    choices = None
    is_serializable = True
    is_inspectable = True

    @property
    def kind(self):
        raise RuntimeError("broken inspect field extraction")

class PyBaseComponent:
    def __init__(self):
        self.base_value = 10

class PyDerivedComponent(PyBaseComponent):
    def __init__(self):
        super().__init__()
        self.child_name = "child"
        self.nullable = 9
        self.rejected = 0

def reject_value(obj, value):
    raise ValueError("setter refused value")

base_fields = {
    "base_value": InspectField(kind="int", label="Base Value")
}
derived_fields = {
    "child_name": InspectField(kind="string", label="Child Name"),
    "nullable": InspectField(kind="nullable", label="Nullable"),
    "rejected": InspectField(kind="int", label="Rejected", setter=reject_value)
}
broken_fields = {
    "good": InspectField(kind="int", label="Good"),
    "broken": BrokenInspectField(),
}
obj = PyDerivedComponent()
)PY";

        int run_rc = PyRun_SimpleString(script);
        if (!require_check(run_rc == 0, "python setup script ran")) return 1;

        nb::module_ main = nb::module_::import_("__main__");
        nb::dict globals = main.attr("__dict__");

        nb::dict base_fields = nb::cast<nb::dict>(globals["base_fields"]);
        nb::dict derived_fields = nb::cast<nb::dict>(globals["derived_fields"]);
        nb::object obj = nb::borrow<nb::object>(globals["obj"]);

        publish_python_inspect_type(
            "PyBaseComponent", nullptr, std::move(base_fields));
        publish_python_inspect_type(
            "PyDerivedComponent", "PyBaseComponent", std::move(derived_fields));

        nb::dict broken_fields = nb::cast<nb::dict>(globals["broken_fields"]);
        bool rejected_new_fields = false;
        try {
            publish_python_inspect_type(
                "PyBrokenComponent",
                nullptr,
                nb::dict(broken_fields)
            );
        } catch (const nb::python_error&) {
            rejected_new_fields = true;
            PyErr_Clear();
        }
        if (!require_check(rejected_new_fields, "broken Python field extraction is rejected")) return 1;
        if (!require_check(!tc_runtime_type_registry_has_type("PyBrokenComponent"),
                           "broken Python field extraction creates no type shell")) return 1;

        bool rejected_replacement = false;
        try {
            publish_python_inspect_type(
                "PyBaseComponent",
                nullptr,
                std::move(broken_fields),
                true
            );
        } catch (const nb::python_error&) {
            rejected_replacement = true;
            PyErr_Clear();
        }
        if (!require_check(rejected_replacement, "broken Python replacement is rejected")) return 1;
        if (!require_check(reg.all_fields_count("PyBaseComponent") == 1,
                           "failed Python replacement preserves committed fields")) return 1;
        if (!require_check(reg.find_field("PyBaseComponent", "base_value") != nullptr,
                           "failed Python replacement preserves old callbacks")) return 1;

        if (!require_check(reg.get_type_backend("PyBaseComponent") == tc::TypeBackend::Python,
                           "base component backend is Python")) return 1;
        if (!require_check(reg.get_type_backend("PyDerivedComponent") == tc::TypeBackend::Python,
                           "derived component backend is Python")) return 1;
        if (!require_check(reg.all_fields_count("PyDerivedComponent") == 4,
                           "derived component inherits and exposes all fields")) return 1;
        if (!require_check(reg.find_field("PyDerivedComponent", "base_value") != nullptr,
                           "derived component exposes inherited field")) return 1;
        if (!require_check(reg.find_field("PyDerivedComponent", "child_name") != nullptr,
                           "derived component exposes own field")) return 1;

        nb::object base_v = tc::InspectRegistry_get(reg, obj.ptr(), "PyDerivedComponent", "base_value");
        if (!require_check(nb::cast<int>(base_v) == 10, "initial inherited value reads through registry")) return 1;

        tc::InspectRegistry_set(reg, obj.ptr(), "PyDerivedComponent", "base_value", nb::int_(42), nullptr);
        tc::InspectRegistry_set(reg, obj.ptr(), "PyDerivedComponent", "child_name", nb::str("updated"), nullptr);
        if (!require_check(nb::cast<int>(nb::getattr(obj, "base_value")) == 42,
                           "inherited value writes through registry")) return 1;
        if (!require_check(nb::cast<std::string>(nb::getattr(obj, "child_name")) == "updated",
                           "own string value writes through registry")) return 1;

        if (!require_check(tc_inspect_set_checked(
                               obj.ptr(), "PyDerivedComponent", "nullable", tc_value_nil(), nullptr),
                           "checked Python setter accepts nil as a value")) return 1;
        if (!require_check(nb::getattr(obj, "nullable").is_none(),
                           "nil assignment stores Python None")) return 1;
        if (!require_check(!tc_inspect_set_checked(
                               obj.ptr(), "PyDerivedComponent", "rejected", tc_value_int(8), nullptr),
                           "checked Python setter reports callback exception")) return 1;
        if (!require_check(!tc_inspect_set_checked(
                               obj.ptr(), "PyDerivedComponent", "missing", tc_value_int(8), nullptr),
                           "checked Python setter reports a missing field")) return 1;

        tc_value serialized = reg.serialize_all(obj.ptr(), "PyDerivedComponent");
        if (!require_check(serialized.type == TC_VALUE_DICT, "serialize_all returns dict")) return 1;
        tc_value* base_field = tc_value_dict_get(&serialized, "base_value");
        tc_value* child_field = tc_value_dict_get(&serialized, "child_name");
        if (!require_check(base_field && base_field->type == TC_VALUE_INT && base_field->data.i == 42,
                           "serialized inherited int field matches")) return 1;
        if (!require_check(child_field && child_field->type == TC_VALUE_STRING,
                           "serialized own string field exists")) return 1;
        if (!require_check(std::string(child_field->data.s) == "updated",
                           "serialized own string field matches")) return 1;
        tc_value_free(&serialized);

        nb::dict input;
        input["base_value"] = nb::int_(7);
        input["child_name"] = nb::str("restored");
        tc::InspectRegistry_deserialize_all_py(reg, obj.ptr(), "PyDerivedComponent", input, nullptr);

        if (!require_check(nb::cast<int>(nb::getattr(obj, "base_value")) == 7,
                           "deserialize_all updates inherited field")) return 1;
        if (!require_check(nb::cast<std::string>(nb::getattr(obj, "child_name")) == "restored",
                           "deserialize_all updates own field")) return 1;

        const char* action_script = R"PY(
action_calls = []
def inspect_action(obj):
    action_calls.append(obj)

action_fields = {
    "run": InspectField(kind="button", label="Run", action=inspect_action, is_serializable=False)
}
)PY";
        run_rc = PyRun_SimpleString(action_script);
        if (!require_check(run_rc == 0, "python action setup script ran")) return 1;

        globals = main.attr("__dict__");
        nb::object inspect_action = nb::borrow<nb::object>(globals["inspect_action"]);
        Py_ssize_t action_refcount = Py_REFCNT(inspect_action.ptr());

        nb::dict action_fields = nb::cast<nb::dict>(globals["action_fields"]);
        publish_python_inspect_type(
            "PyActionComponent", nullptr, std::move(action_fields));
        if (!require_check(Py_REFCNT(inspect_action.ptr()) == action_refcount + 1,
                           "registered action field owns one callable reference")) return 1;
        tc_runtime_type_registry_unregister_type("PyActionComponent");
        if (!require_check(Py_REFCNT(inspect_action.ptr()) == action_refcount,
                           "unregister_type releases action field callable reference")) return 1;

        tc_runtime_type_registry_unregister_type("PyDerivedComponent");
        tc_runtime_type_registry_unregister_type("PyBaseComponent");
    }

    tc::KindRegistry::instance().clear_python();
    Py_Finalize();
    return 0;
}
