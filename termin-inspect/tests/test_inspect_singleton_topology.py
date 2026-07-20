import pytest

from termin.inspect import _inspect_native as inspect_canonical


@pytest.fixture(scope="module", autouse=True)
def _component_runtime():
    import termin.bootstrap

    termin.bootstrap.bootstrap_player()
    yield
    termin.bootstrap.shutdown_player()


def test_inspect_singleton_topology_addresses():
    inspect_addr_canonical = inspect_canonical.inspect_registry_address()
    assert inspect_addr_canonical != 0

    kind_addr_canonical = inspect_canonical.kind_registry_cpp_address()
    assert kind_addr_canonical != 0


def test_python_component_without_own_fields_inherits_base_inspect_fields():
    from termin.inspect import InspectRegistry, TypeBackend
    from termin.scene import PythonComponent, publish_python_component

    registry = InspectRegistry.instance()
    class NoOwnInspectFieldsProbeComponent(PythonComponent):
        pass

    publish_python_component(NoOwnInspectFieldsProbeComponent)

    field_paths = {field.path for field in registry.all_fields("NoOwnInspectFieldsProbeComponent")}

    assert registry.has_type("PythonComponent")
    assert registry.has_type("NoOwnInspectFieldsProbeComponent")
    assert registry.get_type_parent("NoOwnInspectFieldsProbeComponent") == "PythonComponent"
    assert registry.get_type_backend("NoOwnInspectFieldsProbeComponent") == TypeBackend.Python
    assert "enabled" in field_paths


def test_inspect_registry_does_not_publish_incremental_mutators():
    from termin.inspect import InspectRegistry

    registry = InspectRegistry.instance()
    for name in (
        "register_python_fields",
        "set_type_parent",
        "set_type_metadata",
        "add_button",
        "unregister_type",
    ):
        assert not hasattr(registry, name)
