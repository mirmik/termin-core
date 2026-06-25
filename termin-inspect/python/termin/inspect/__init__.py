# termin.inspect - inspection and field metadata
from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_base", "termin_inspect")

from termin.inspect.inspect_field import InspectAttr, InspectField, inspect
from termin.inspect.kind import KindRegistry, register_kind
from termin.inspect.registry import InspectRegistry, InspectFieldInfo, TypeBackend, EnumChoice

__all__ = [
    "InspectField",
    "InspectAttr",
    "inspect",
    "InspectRegistry",
    "InspectFieldInfo",
    "TypeBackend",
    "EnumChoice",
    "KindRegistry",
    "register_kind",
]
