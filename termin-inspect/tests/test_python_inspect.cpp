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

} // namespace

int main() {
    tc::init_cpp_inspect_vtable();
    (void)tc::KindRegistryCpp::instance();
    tc::register_builtin_cpp_kinds();
    tc::init_python_lang_vtable();

    Py_Initialize();
    {
        auto& reg = tc::InspectRegistry::instance();
        reg.unregister_type("PyBaseComponent");
        reg.unregister_type("PyDerivedComponent");

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

class PyBaseComponent:
    def __init__(self):
        self.base_value = 10

class PyDerivedComponent(PyBaseComponent):
    def __init__(self):
        super().__init__()
        self.child_name = "child"

base_fields = {
    "base_value": InspectField(kind="int", label="Base Value")
}
derived_fields = {
    "child_name": InspectField(kind="string", label="Child Name")
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

        tc::InspectRegistry_register_python_fields(reg, "PyBaseComponent", std::move(base_fields));
        tc::InspectRegistry_register_python_fields(reg, "PyDerivedComponent", std::move(derived_fields));
        reg.set_type_parent("PyDerivedComponent", "PyBaseComponent");

        if (!require_check(reg.get_type_backend("PyBaseComponent") == tc::TypeBackend::Python,
                           "base component backend is Python")) return 1;
        if (!require_check(reg.get_type_backend("PyDerivedComponent") == tc::TypeBackend::Python,
                           "derived component backend is Python")) return 1;
        if (!require_check(reg.all_fields_count("PyDerivedComponent") == 2,
                           "derived component inherits two fields")) return 1;
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
    }

    tc::KindRegistry::instance().clear_python();
    Py_Finalize();
    return 0;
}
