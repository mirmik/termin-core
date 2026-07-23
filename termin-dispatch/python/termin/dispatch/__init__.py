"""Caller-driven deferred execution without thread ownership policy."""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_dispatch")

from ._dispatch_native import DeferredCall, Dispatcher, DispatchStats

__all__ = ["DeferredCall", "Dispatcher", "DispatchStats"]
