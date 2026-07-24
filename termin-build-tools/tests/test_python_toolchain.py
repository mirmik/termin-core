from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

from termin_build.python_abi import PythonAbiIdentity
from termin_build import python_toolchain


def _artifact(*, sha256: str) -> python_toolchain.PythonToolchainArtifact:
    return python_toolchain.PythonToolchainArtifact(
        kind="source",
        url="https://example.invalid/Python-3.14.6.tar.xz",
        sha256=sha256,
        archive_root="Python-3.14.6",
        configure_args=("--disable-gil",),
    )


def test_repository_lock_pins_free_threaded_cpython_314():
    repo_root = Path(__file__).resolve().parents[2]

    lock = python_toolchain.PythonToolchainLock.load(
        repo_root / python_toolchain.LOCK_RELATIVE_PATH
    )

    assert lock.version == "3.14.6"
    assert lock.abi_version == "3.14"
    assert lock.free_threaded is True
    assert lock.py_gil_disabled is True
    assert lock.platforms["linux-x86_64"].configure_args[0] == "--disable-gil"
    assert lock.platforms["windows-x86_64"].kind == "nuget"


def test_lock_rejects_a_gil_enabled_canonical_profile(tmp_path):
    lock_path = tmp_path / "lock.json"
    lock_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "version": "3.14.6",
                "python_abi": {
                    "version": "3.14",
                    "free_threaded": False,
                    "py_gil_disabled": False,
                },
                "platforms": {
                    "linux-x86_64": {
                        "kind": "source",
                        "url": "https://example.invalid/python.tar.xz",
                        "sha256": "0" * 64,
                        "archive_root": "Python-3.14.6",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        python_toolchain.PythonToolchainError,
        match="must be free-threaded",
    ):
        python_toolchain.PythonToolchainLock.load(lock_path)


def test_download_uses_verified_cached_artifact_offline(tmp_path, monkeypatch):
    payload = b"canonical CPython archive"
    artifact = _artifact(sha256=hashlib.sha256(payload).hexdigest())
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    cached = downloads / artifact.filename
    cached.write_bytes(payload)
    monkeypatch.setenv("TERMIN_PYTHON_TOOLCHAIN_OFFLINE", "1")

    assert python_toolchain._download_artifact(artifact, downloads) == cached


def test_download_rejects_corrupt_cached_artifact(tmp_path):
    artifact = _artifact(sha256="0" * 64)
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / artifact.filename).write_bytes(b"corrupt")

    with pytest.raises(
        python_toolchain.PythonToolchainError,
        match="cached Python toolchain artifact hash mismatch",
    ):
        python_toolchain._download_artifact(artifact, downloads)


def test_zip_extraction_rejects_parent_traversal(tmp_path):
    archive = tmp_path / "python.nupkg"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../escape.txt", "bad")

    with pytest.raises(
        python_toolchain.PythonToolchainError,
        match="escapes extraction root",
    ):
        python_toolchain._extract_zip(archive, tmp_path / "runtime")


def test_probe_identity_reads_free_threaded_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(
        python_toolchain.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "version": "3.14",
                    "soabi": "cpython-314t-x86_64-linux-gnu",
                    "free_threaded": True,
                    "py_gil_disabled": True,
                    "gil_enabled": False,
                    "abiflags": "t",
                }
            ),
            stderr="",
        ),
    )

    identity, gil_enabled, abiflags = python_toolchain._probe_identity(
        tmp_path / "python3.14t"
    )

    assert identity.wheel_abi_tag == "cp314t"
    assert gil_enabled is False
    assert abiflags == "t"


def test_ensure_toolchain_rejects_runtime_that_starts_with_gil(
    tmp_path,
    monkeypatch,
):
    lock_path = tmp_path / python_toolchain.LOCK_RELATIVE_PATH
    lock_path.parent.mkdir(parents=True)
    source_lock = Path(__file__).resolve().parents[2] / python_toolchain.LOCK_RELATIVE_PATH
    lock_path.write_bytes(source_lock.read_bytes())
    artifact_path = tmp_path / "archive"
    artifact_path.write_bytes(b"archive")
    runtime_root = tmp_path / "runtime"
    python_executable = runtime_root / "bin" / "python3.14t"
    python_executable.parent.mkdir(parents=True)
    python_executable.touch()
    identity = PythonAbiIdentity(
        version="3.14",
        soabi="cpython-314t-x86_64-linux-gnu",
        free_threaded=True,
        py_gil_disabled=True,
    )
    monkeypatch.setattr(python_toolchain, "platform_key", lambda: "linux-x86_64")
    monkeypatch.setattr(
        python_toolchain,
        "_download_artifact",
        lambda *_args: artifact_path,
    )
    monkeypatch.setattr(
        python_toolchain,
        "_build_linux_runtime",
        lambda *_args: runtime_root,
    )
    monkeypatch.setattr(
        python_toolchain,
        "_probe_identity",
        lambda _python: (identity, True, "t"),
    )

    with pytest.raises(
        python_toolchain.PythonToolchainError,
        match="started with the GIL enabled",
    ):
        python_toolchain.ensure_python_toolchain(tmp_path)


def test_ensure_toolchain_writes_reproducibility_manifest(
    tmp_path,
    monkeypatch,
):
    lock_path = tmp_path / python_toolchain.LOCK_RELATIVE_PATH
    lock_path.parent.mkdir(parents=True)
    source_lock = Path(__file__).resolve().parents[2] / python_toolchain.LOCK_RELATIVE_PATH
    lock_path.write_bytes(source_lock.read_bytes())
    artifact_path = tmp_path / "archive"
    artifact_path.write_bytes(b"archive")
    runtime_root = tmp_path / "runtime"
    python_executable = runtime_root / "bin" / "python3.14t"
    python_executable.parent.mkdir(parents=True)
    python_executable.touch()
    identity = PythonAbiIdentity(
        version="3.14",
        soabi="cpython-314t-x86_64-linux-gnu",
        free_threaded=True,
        py_gil_disabled=True,
    )
    monkeypatch.setattr(python_toolchain, "platform_key", lambda: "linux-x86_64")
    monkeypatch.setattr(
        python_toolchain,
        "_download_artifact",
        lambda *_args: artifact_path,
    )
    monkeypatch.setattr(
        python_toolchain,
        "_build_linux_runtime",
        lambda *_args: runtime_root,
    )
    monkeypatch.setattr(
        python_toolchain,
        "_probe_identity",
        lambda _python: (identity, False, "t"),
    )

    toolchain = python_toolchain.ensure_python_toolchain(tmp_path)

    manifest = json.loads(
        (runtime_root / python_toolchain.MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert toolchain.python_executable == python_executable
    assert manifest["version"] == "3.14.6"
    assert manifest["python_abi"] == identity.to_dict()
    assert manifest["python_executable"] == "bin/python3.14t"
