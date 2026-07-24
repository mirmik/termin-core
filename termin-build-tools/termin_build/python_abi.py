"""Canonical Python ABI identity used by Termin build and runtime manifests."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import sys
import sysconfig
from typing import Mapping


class PythonAbiError(RuntimeError):
    """Raised when Python ABI metadata is missing, malformed, or incompatible."""


_VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")
_CPYTHON_SOABI_PATTERNS = (
    re.compile(r"^cpython-(\d+)(t?)(?:-|$)"),
    re.compile(r"^cp(\d+)(t?)(?:-|$)"),
)


@dataclass(frozen=True)
class PythonAbiIdentity:
    version: str
    soabi: str
    free_threaded: bool
    py_gil_disabled: bool

    def __post_init__(self) -> None:
        version_match = _VERSION_RE.fullmatch(self.version)
        if version_match is None:
            raise PythonAbiError(
                f"Python ABI version must use major.minor form, got {self.version!r}"
            )
        if not self.soabi or self.soabi == "unknown":
            raise PythonAbiError("Python ABI SOABI must be a non-empty known value")
        if self.free_threaded != self.py_gil_disabled:
            raise PythonAbiError(
                "Python ABI free_threaded and py_gil_disabled markers disagree"
            )

        soabi_match = next(
            (
                match
                for pattern in _CPYTHON_SOABI_PATTERNS
                if (match := pattern.match(self.soabi)) is not None
            ),
            None,
        )
        if soabi_match is None:
            raise PythonAbiError(
                f"unsupported CPython SOABI format: {self.soabi!r}"
            )
        expected_digits = "".join(version_match.groups())
        if soabi_match.group(1) != expected_digits:
            raise PythonAbiError(
                f"Python ABI version {self.version!r} disagrees with "
                f"SOABI {self.soabi!r}"
            )
        soabi_free_threaded = soabi_match.group(2) == "t"
        if soabi_free_threaded != self.free_threaded:
            raise PythonAbiError(
                f"Python ABI free_threaded={self.free_threaded!r} disagrees "
                f"with SOABI {self.soabi!r}"
            )

    @classmethod
    def from_mapping(
        cls,
        value: object,
        *,
        context: str = "Python ABI",
    ) -> "PythonAbiIdentity":
        if not isinstance(value, Mapping):
            raise PythonAbiError(f"{context} must be an object")
        required = {
            "version": str,
            "soabi": str,
            "free_threaded": bool,
            "py_gil_disabled": bool,
        }
        for field, expected_type in required.items():
            field_value = value.get(field)
            if type(field_value) is not expected_type:
                raise PythonAbiError(
                    f"{context}.{field} must be {expected_type.__name__}"
                )
        try:
            return cls(
                version=value["version"],
                soabi=value["soabi"],
                free_threaded=value["free_threaded"],
                py_gil_disabled=value["py_gil_disabled"],
            )
        except PythonAbiError as error:
            raise PythonAbiError(f"{context} is invalid: {error}") from error

    @classmethod
    def current(cls) -> "PythonAbiIdentity":
        gil_disabled = bool(sysconfig.get_config_var("Py_GIL_DISABLED") or 0)
        return cls(
            version=f"{sys.version_info.major}.{sys.version_info.minor}",
            soabi=str(sysconfig.get_config_var("SOABI") or ""),
            free_threaded=gil_disabled,
            py_gil_disabled=gil_disabled,
        )

    @classmethod
    def from_runtime_probe(
        cls,
        value: Mapping[str, object],
        *,
        context: str,
    ) -> "PythonAbiIdentity":
        return cls.from_mapping(
            {
                "version": value.get("version"),
                "soabi": value.get("soabi"),
                "free_threaded": value.get("free_threaded"),
                "py_gil_disabled": value.get("py_gil_disabled"),
            },
            context=context,
        )

    @property
    def wheel_abi_tag(self) -> str:
        match = next(
            (
                candidate
                for pattern in _CPYTHON_SOABI_PATTERNS
                if (candidate := pattern.match(self.soabi)) is not None
            ),
            None,
        )
        if match is None:
            raise PythonAbiError(
                f"cannot derive wheel ABI tag from SOABI {self.soabi!r}"
            )
        return f"cp{match.group(1)}{match.group(2)}"

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "soabi": self.soabi,
            "free_threaded": self.free_threaded,
            "py_gil_disabled": self.py_gil_disabled,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def require_matches(
        self,
        actual: "PythonAbiIdentity",
        *,
        context: str,
    ) -> None:
        if self != actual:
            raise PythonAbiError(
                f"{context} mismatch: expected {self.canonical_json()}, "
                f"got {actual.canonical_json()}"
            )
