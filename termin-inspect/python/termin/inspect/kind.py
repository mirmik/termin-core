"""Python facade for inspect kind serialization handlers."""

from __future__ import annotations

from tcbase import log
from termin.inspect._inspect_native import KindRegistry as _KindRegistry


class KindRegistry:
    """Registry for kind serialization handlers."""

    @staticmethod
    def instance() -> _KindRegistry:
        """Get the singleton instance."""
        return _KindRegistry.instance()

    @staticmethod
    def register_python(name: str, serialize=None, deserialize=None):
        """Register Python handlers for a kind."""
        _KindRegistry.instance().register_python(
            name,
            serialize or (lambda value: None),
            deserialize or (lambda value: None),
        )
        try:
            from termin_modules.module_context import record_python_kind
        except ModuleNotFoundError as exc:
            if exc.name not in ("termin_modules", "termin_modules.module_context"):
                log.error("Failed to load module ownership context", exc_info=True)
            return
        except Exception:
            log.error("Failed to load module ownership context", exc_info=True)
            return

        try:
            record_python_kind(name)
        except Exception:
            log.error(f"Failed to record module ownership for Python kind {name}", exc_info=True)

    @staticmethod
    def unregister_python(name: str):
        """Unregister Python handlers for a kind."""
        return _KindRegistry.instance().unregister_python(name)

    @staticmethod
    def register_type(type_, kind_name: str):
        """Register Python type to kind-name mapping."""
        return _KindRegistry.instance().register_type(type_, kind_name)

    @staticmethod
    def serialize(kind: str, obj):
        """Serialize object using a registered Python handler."""
        return _KindRegistry.instance().serialize(kind, obj)

    @staticmethod
    def deserialize(kind: str, data):
        """Deserialize data using a registered Python handler."""
        return _KindRegistry.instance().deserialize(kind, data)

    @staticmethod
    def kinds():
        """Get all registered kind names."""
        return _KindRegistry.instance().kinds()


def register_kind(name: str):
    """Decorator for registering a kind handler class."""

    def decorator(cls):
        KindRegistry.register_python(
            name,
            serialize=cls.serialize,
            deserialize=cls.deserialize,
        )
        return cls

    return decorator


__all__ = ["KindRegistry", "register_kind"]
