"""Python facade for inspect kind serialization handlers."""

from __future__ import annotations

from termin.inspect._inspect_native import KindRegistry as _KindRegistry


class KindRegistry:
    """Registry for kind serialization handlers."""

    _python_owners: dict[str, str] = {}

    @staticmethod
    def instance() -> _KindRegistry:
        """Get the singleton instance."""
        return _KindRegistry.instance()

    @staticmethod
    def register_python(name: str, serialize=None, deserialize=None, *, owner: str | None = None):
        """Register Python handlers for a kind."""
        serializer = serialize or (lambda value: None)
        if owner is None:
            try:
                from termin_modules.module_context import owner_for_python_module
            except ModuleNotFoundError as exc:
                if exc.name not in ("termin_modules", "termin_modules.module_context"):
                    from tcbase import log

                    log.error("Failed to load module ownership context", exc_info=True)
                owner = "termin-inspect-python"
            except Exception:
                from tcbase import log

                log.error("Failed to load module ownership context", exc_info=True)
                owner = "termin-inspect-python"
            else:
                owner = (
                    owner_for_python_module(serializer.__module__)
                    or "termin-inspect-python"
                )
        _KindRegistry.instance().register_python(
            name,
            serializer,
            deserialize or (lambda value: None),
        )
        KindRegistry._python_owners[name] = owner

    @staticmethod
    def unregister_python(name: str):
        """Unregister Python handlers for a kind."""
        KindRegistry._python_owners.pop(name, None)
        return _KindRegistry.instance().unregister_python(name)

    @staticmethod
    def unregister_owner(owner: str) -> None:
        for name, registered_owner in tuple(KindRegistry._python_owners.items()):
            if registered_owner == owner:
                KindRegistry.unregister_python(name)

    @staticmethod
    def list_owned(owner: str) -> list[str]:
        return sorted(
            name
            for name, registered_owner in KindRegistry._python_owners.items()
            if registered_owner == owner
        )

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
