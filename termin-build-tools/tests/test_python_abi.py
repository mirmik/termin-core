from __future__ import annotations

import pytest

from termin_build.python_abi import PythonAbiError, PythonAbiIdentity
from termin_build.sdk_verification import _require_wheel_python_abi


CP314 = PythonAbiIdentity(
    version="3.14",
    soabi="cpython-314-x86_64-linux-gnu",
    free_threaded=False,
    py_gil_disabled=False,
)
CP314T = PythonAbiIdentity(
    version="3.14",
    soabi="cpython-314t-x86_64-linux-gnu",
    free_threaded=True,
    py_gil_disabled=True,
)


def test_cp314t_identity_round_trips_and_exposes_wheel_abi() -> None:
    assert PythonAbiIdentity.from_mapping(CP314T.to_dict()) == CP314T
    assert CP314T.wheel_abi_tag == "cp314t"


def test_cp314_and_cp314t_are_incompatible() -> None:
    with pytest.raises(PythonAbiError, match="mismatch"):
        CP314T.require_matches(CP314, context="SDK/runtime Python ABI")


def test_cp314t_wheel_validation_rejects_regular_cp314_native_abi() -> None:
    _require_wheel_python_abi({"cp314t"}, CP314T, wheel_name="good.whl")
    _require_wheel_python_abi({"none"}, CP314T, wheel_name="pure.whl")

    with pytest.raises(RuntimeError, match="expected cp314t, got cp314"):
        _require_wheel_python_abi({"cp314"}, CP314T, wheel_name="wrong.whl")


@pytest.mark.parametrize(
    "value, match",
    [
        (
            {
                "version": "3.14",
                "soabi": "cpython-314t-x86_64-linux-gnu",
                "free_threaded": False,
                "py_gil_disabled": False,
            },
            "disagrees with SOABI",
        ),
        (
            {
                "version": "3.14",
                "soabi": "cpython-314t-x86_64-linux-gnu",
                "free_threaded": True,
                "py_gil_disabled": False,
            },
            "markers disagree",
        ),
        (
            {
                "version": "3.14",
                "soabi": "cpython-313t-x86_64-linux-gnu",
                "free_threaded": True,
                "py_gil_disabled": True,
            },
            "disagrees with SOABI",
        ),
    ],
)
def test_identity_rejects_internally_inconsistent_metadata(
    value: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(PythonAbiError, match=match):
        PythonAbiIdentity.from_mapping(value)
