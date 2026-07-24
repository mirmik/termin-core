from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from termin_build.python_abi import PythonAbiIdentity
from termin_build.wheelhouse import WheelhouseError, validate_locked_wheelhouse


CP314T = PythonAbiIdentity(
    version="3.14",
    soabi="cpython-314t-x86_64-linux-gnu",
    free_threaded=True,
    py_gil_disabled=True,
)


def _write_wheel(
    wheel_dir: Path,
    *,
    name: str,
    version: str,
    tag: str,
) -> Path:
    normalized = name.replace("-", "_")
    path = wheel_dir / f"{normalized}-{version}-{tag}.whl"
    dist_info = f"{normalized}-{version}.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
        )
        archive.writestr(
            f"{dist_info}/WHEEL",
            f"Wheel-Version: 1.0\nTag: {tag}\n",
        )
    return path


def test_locked_wheelhouse_accepts_exact_cp314t_and_pure_wheels(tmp_path: Path) -> None:
    _write_wheel(
        tmp_path,
        name="numpy",
        version="2.5.1",
        tag="cp314-cp314t-manylinux_2_28_x86_64",
    )
    _write_wheel(
        tmp_path,
        name="packaging",
        version="26.2",
        tag="py3-none-any",
    )

    validate_locked_wheelhouse(
        tmp_path,
        {
            "numpy": ("numpy", "2.5.1"),
            "packaging": ("packaging", "26.2"),
        },
        python_abi=CP314T,
        supported_tags={
            "cp314-cp314t-manylinux_2_28_x86_64",
            "py3-none-any",
        },
    )


def test_locked_wheelhouse_rejects_regular_cp314_native_wheel(tmp_path: Path) -> None:
    _write_wheel(
        tmp_path,
        name="numpy",
        version="2.5.1",
        tag="cp314-cp314-manylinux_2_28_x86_64",
    )

    with pytest.raises(WheelhouseError, match="expected cp314t, got cp314"):
        validate_locked_wheelhouse(
            tmp_path,
            {"numpy": ("numpy", "2.5.1")},
            python_abi=CP314T,
            supported_tags={"cp314-cp314t-manylinux_2_28_x86_64"},
        )


def test_locked_wheelhouse_reports_missing_and_stale_artifacts(tmp_path: Path) -> None:
    stale = _write_wheel(
        tmp_path,
        name="numpy",
        version="2.2.6",
        tag="cp314-cp314t-manylinux_2_28_x86_64",
    )

    with pytest.raises(WheelhouseError) as raised:
        validate_locked_wheelhouse(
            tmp_path,
            {
                "numpy": ("numpy", "2.5.1"),
                "scipy": ("scipy", "1.18.0"),
            },
            python_abi=CP314T,
            supported_tags={"cp314-cp314t-manylinux_2_28_x86_64"},
        )

    message = str(raised.value)
    assert "numpy==2.5.1 wheel, found 0" in message
    assert "scipy==1.18.0 wheel, found 0" in message
    assert f"outside the exact lock: {stale.name}" in message
