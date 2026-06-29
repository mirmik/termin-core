import sys

from termin.inspect import _inspect_native as inspect_canonical


def test_inspect_singleton_topology_addresses():
    inspect_addr_canonical = inspect_canonical.inspect_registry_address()
    assert inspect_addr_canonical != 0

    kind_addr_canonical = inspect_canonical.kind_registry_cpp_address()
    assert kind_addr_canonical != 0


def test_python_component_without_own_fields_inherits_base_inspect_fields():
    from termin.inspect import InspectRegistry, TypeBackend
    from termin.scene import PythonComponent

    registry = InspectRegistry.instance()
    registry.unregister_type("NoOwnInspectFieldsProbeComponent")

    class NoOwnInspectFieldsProbeComponent(PythonComponent):
        pass

    field_paths = {field.path for field in registry.all_fields("NoOwnInspectFieldsProbeComponent")}

    assert registry.has_type("PythonComponent")
    assert registry.has_type("NoOwnInspectFieldsProbeComponent")
    assert registry.get_type_parent("NoOwnInspectFieldsProbeComponent") == "PythonComponent"
    assert registry.get_type_backend("NoOwnInspectFieldsProbeComponent") == TypeBackend.Python
    assert "enabled" in field_paths


def test_unregister_type_releases_python_action_field_reference():
    from termin.inspect import InspectField, InspectRegistry

    registry = InspectRegistry.instance()
    registry.unregister_type("ActionRefcountProbe")

    def inspect_action(_obj):
        return None

    baseline_refcount = sys.getrefcount(inspect_action)
    registry.register_python_fields(
        "ActionRefcountProbe",
        {
            "run": InspectField(
                label="Run",
                kind="button",
                action=inspect_action,
                is_serializable=False,
            )
        },
    )
    assert sys.getrefcount(inspect_action) == baseline_refcount + 1

    registry.unregister_type("ActionRefcountProbe")
    assert sys.getrefcount(inspect_action) == baseline_refcount
