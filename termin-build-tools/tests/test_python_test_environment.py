from __future__ import annotations

import json
from pathlib import Path

import pytest

from termin_build import python_test_environment
from termin_build.python_abi import PythonAbiIdentity


def _write_requirements(path: Path, requirements: dict[str, str]) -> None:
    path.write_text(
        "".join(f"{name}=={version}\n" for name, version in requirements.items()),
        encoding="utf-8",
    )


def _write_distribution(site_packages: Path, name: str, version: str) -> None:
    metadata = site_packages / f"{name}-{version}.dist-info" / "METADATA"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
        encoding="utf-8",
    )
    package = site_packages / name.replace("-", "_")
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")


def _fake_install(
    requirements: dict[str, str],
    calls: list[Path],
):
    def install(
        _installer_python: Path,
        _requirements_path: Path,
        target: Path,
    ) -> None:
        calls.append(target)
        for name, version in requirements.items():
            _write_distribution(target, name, version)

    return install


def test_prepare_reuses_environment_with_matching_lock_and_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment_root = tmp_path / "environment"
    requirements = tmp_path / "requirements.txt"
    locked = {"ruff": "1.2.3", "scipy": "4.5.6"}
    _write_requirements(requirements, locked)
    identity = python_test_environment.RuntimeIdentity.current()
    monkeypatch.setattr(
        python_test_environment,
        "probe_runtime_identity",
        lambda _executable: identity,
    )
    calls: list[Path] = []
    install = _fake_install(locked, calls)

    assert python_test_environment.prepare_test_environment(
        environment_root,
        requirements,
        tmp_path / "python",
        install=install,
    )
    assert not python_test_environment.prepare_test_environment(
        environment_root,
        requirements,
        tmp_path / "python",
        install=install,
    )
    assert len(calls) == 1
    assert python_test_environment.validate_test_environment(
        environment_root,
        requirements,
    )["runtime"] == identity.to_dict()


def test_prepare_rebuilds_and_prunes_unlocked_distribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment_root = tmp_path / "environment"
    site_packages = environment_root / python_test_environment.SITE_PACKAGES_NAME
    requirements = tmp_path / "requirements.txt"
    locked = {"scipy": "4.5.6"}
    _write_requirements(requirements, locked)
    identity = python_test_environment.RuntimeIdentity.current()
    monkeypatch.setattr(
        python_test_environment,
        "probe_runtime_identity",
        lambda _executable: identity,
    )
    calls: list[Path] = []
    install = _fake_install(locked, calls)
    python_test_environment.prepare_test_environment(
        environment_root,
        requirements,
        tmp_path / "python",
        install=install,
    )
    _write_distribution(site_packages, "numpy", "2.2.6")

    assert python_test_environment.prepare_test_environment(
        environment_root,
        requirements,
        tmp_path / "python",
        install=install,
    )
    assert len(calls) == 2
    assert not (site_packages / "numpy-2.2.6.dist-info").exists()
    assert python_test_environment._installed_distributions(site_packages) == locked


def test_prepare_rejects_installer_with_different_abi(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requirements = tmp_path / "requirements.txt"
    _write_requirements(requirements, {"ruff": "1.2.3"})
    current = python_test_environment.RuntimeIdentity.current()
    mismatched = python_test_environment.RuntimeIdentity(
        python_abi=PythonAbiIdentity(
            version="3.10",
            soabi="cpython-310-x86_64-linux-gnu",
            free_threaded=False,
            py_gil_disabled=False,
        ),
        platform=current.platform,
        machine=current.machine,
    )
    monkeypatch.setattr(
        python_test_environment,
        "probe_runtime_identity",
        lambda _executable: mismatched,
    )

    with pytest.raises(
        python_test_environment.PythonTestEnvironmentError,
        match="runtime mismatch",
    ):
        python_test_environment.prepare_test_environment(
            tmp_path / "environment",
            requirements,
            tmp_path / "python",
        )


def test_failed_rebuild_preserves_previous_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment_root = tmp_path / "environment"
    site_packages = environment_root / python_test_environment.SITE_PACKAGES_NAME
    requirements = tmp_path / "requirements.txt"
    locked = {"ruff": "1.2.3"}
    _write_requirements(requirements, locked)
    identity = python_test_environment.RuntimeIdentity.current()
    monkeypatch.setattr(
        python_test_environment,
        "probe_runtime_identity",
        lambda _executable: identity,
    )
    python_test_environment.prepare_test_environment(
        environment_root,
        requirements,
        tmp_path / "python",
        install=_fake_install(locked, []),
    )
    manifest_before = (
        environment_root / python_test_environment.MANIFEST_NAME
    ).read_text(encoding="utf-8")

    def fail_install(
        _installer_python: Path,
        _requirements_path: Path,
        target: Path,
    ) -> None:
        (target / "partial").write_text("broken", encoding="utf-8")
        raise python_test_environment.PythonTestEnvironmentError("install failed")

    with pytest.raises(
        python_test_environment.PythonTestEnvironmentError,
        match="install failed",
    ):
        python_test_environment.prepare_test_environment(
            environment_root,
            requirements,
            tmp_path / "python",
            force=True,
            install=fail_install,
        )

    assert (site_packages / "ruff").is_dir()
    assert (
        environment_root / python_test_environment.MANIFEST_NAME
    ).read_text(encoding="utf-8") == manifest_before


def test_validation_rejects_changed_requirements(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment_root = tmp_path / "environment"
    requirements = tmp_path / "requirements.txt"
    locked = {"ruff": "1.2.3"}
    _write_requirements(requirements, locked)
    identity = python_test_environment.RuntimeIdentity.current()
    monkeypatch.setattr(
        python_test_environment,
        "probe_runtime_identity",
        lambda _executable: identity,
    )
    python_test_environment.prepare_test_environment(
        environment_root,
        requirements,
        tmp_path / "python",
        install=_fake_install(locked, []),
    )
    _write_requirements(requirements, {"ruff": "1.2.4"})

    with pytest.raises(
        python_test_environment.PythonTestEnvironmentError,
        match="requirements changed",
    ):
        python_test_environment.validate_test_environment(
            environment_root,
            requirements,
        )


def test_manifest_is_stable_json(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    _write_requirements(requirements, {"ruff": "1.2.3"})

    manifest = python_test_environment._expected_manifest(
        requirements,
        python_test_environment.RuntimeIdentity.current(),
    )

    assert json.loads(json.dumps(manifest)) == manifest
