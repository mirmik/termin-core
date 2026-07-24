"""Pinned CPython toolchain acquisition, build, and identity verification."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Mapping
from urllib.request import urlopen
import zipfile

from .python_abi import PythonAbiError, PythonAbiIdentity


LOCK_RELATIVE_PATH = Path("build-system/python-toolchain-lock.json")
MANIFEST_NAME = "termin-python-toolchain.json"
SCHEMA_VERSION = 1
BUILD_RECIPE_VERSION = 3


class PythonToolchainError(RuntimeError):
    """Raised when the pinned CPython toolchain cannot be materialized."""


@dataclass(frozen=True)
class PythonToolchainArtifact:
    kind: str
    url: str
    sha256: str
    archive_root: str | None = None
    runtime_root: str | None = None
    configure_args: tuple[str, ...] = ()

    @classmethod
    def from_mapping(
        cls,
        value: object,
        *,
        context: str,
    ) -> "PythonToolchainArtifact":
        if not isinstance(value, Mapping):
            raise PythonToolchainError(f"{context} must be an object")
        kind = value.get("kind")
        url = value.get("url")
        sha256 = value.get("sha256")
        if kind not in {"source", "nuget"}:
            raise PythonToolchainError(f"{context}.kind must be source or nuget")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise PythonToolchainError(f"{context}.url must be an HTTPS URL")
        if (
            not isinstance(sha256, str)
            or len(sha256) != 64
            or any(character not in "0123456789abcdef" for character in sha256)
        ):
            raise PythonToolchainError(
                f"{context}.sha256 must be a lowercase SHA-256 digest"
            )
        archive_root = value.get("archive_root")
        runtime_root = value.get("runtime_root")
        configure_args = value.get("configure_args", [])
        if archive_root is not None and not isinstance(archive_root, str):
            raise PythonToolchainError(f"{context}.archive_root must be a string")
        if runtime_root is not None and not isinstance(runtime_root, str):
            raise PythonToolchainError(f"{context}.runtime_root must be a string")
        if (
            not isinstance(configure_args, list)
            or not all(isinstance(item, str) for item in configure_args)
        ):
            raise PythonToolchainError(
                f"{context}.configure_args must be an array of strings"
            )
        if kind == "source" and not archive_root:
            raise PythonToolchainError(
                f"{context}.archive_root is required for source artifacts"
            )
        if kind == "nuget" and not runtime_root:
            raise PythonToolchainError(
                f"{context}.runtime_root is required for NuGet artifacts"
            )
        return cls(
            kind=kind,
            url=url,
            sha256=sha256,
            archive_root=archive_root,
            runtime_root=runtime_root,
            configure_args=tuple(configure_args),
        )

    @property
    def filename(self) -> str:
        filename = self.url.rsplit("/", 1)[-1]
        if not filename:
            raise PythonToolchainError(f"toolchain URL has no filename: {self.url}")
        return filename

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "kind": self.kind,
            "url": self.url,
            "sha256": self.sha256,
        }
        if self.archive_root is not None:
            result["archive_root"] = self.archive_root
        if self.runtime_root is not None:
            result["runtime_root"] = self.runtime_root
        if self.configure_args:
            result["configure_args"] = list(self.configure_args)
        return result


@dataclass(frozen=True)
class PythonToolchainLock:
    version: str
    abi_version: str
    free_threaded: bool
    py_gil_disabled: bool
    platforms: Mapping[str, PythonToolchainArtifact]

    @classmethod
    def load(cls, path: Path) -> "PythonToolchainLock":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PythonToolchainError(
                f"failed to read Python toolchain lock {path}: {error}"
            ) from error
        if not isinstance(value, dict) or value.get("schema") != SCHEMA_VERSION:
            raise PythonToolchainError(
                f"unsupported Python toolchain lock schema in {path}"
            )
        version = value.get("version")
        abi = value.get("python_abi")
        platforms = value.get("platforms")
        if not isinstance(version, str):
            raise PythonToolchainError("Python toolchain version must be a string")
        if not isinstance(abi, dict):
            raise PythonToolchainError("Python toolchain python_abi must be an object")
        abi_version = abi.get("version")
        free_threaded = abi.get("free_threaded")
        py_gil_disabled = abi.get("py_gil_disabled")
        if not isinstance(abi_version, str):
            raise PythonToolchainError("Python toolchain ABI version must be a string")
        if type(free_threaded) is not bool or type(py_gil_disabled) is not bool:
            raise PythonToolchainError(
                "Python toolchain free-threaded markers must be booleans"
            )
        if not version.startswith(f"{abi_version}."):
            raise PythonToolchainError(
                f"Python version {version!r} disagrees with ABI {abi_version!r}"
            )
        if not free_threaded or not py_gil_disabled:
            raise PythonToolchainError(
                "canonical Python toolchain must be free-threaded"
            )
        if not isinstance(platforms, dict) or not platforms:
            raise PythonToolchainError(
                "Python toolchain platforms must be a non-empty object"
            )
        parsed_platforms = {
            key: PythonToolchainArtifact.from_mapping(
                artifact,
                context=f"Python toolchain platforms.{key}",
            )
            for key, artifact in platforms.items()
            if isinstance(key, str)
        }
        if len(parsed_platforms) != len(platforms):
            raise PythonToolchainError("Python toolchain platform names must be strings")
        return cls(
            version=version,
            abi_version=abi_version,
            free_threaded=free_threaded,
            py_gil_disabled=py_gil_disabled,
            platforms=parsed_platforms,
        )


@dataclass(frozen=True)
class PythonToolchain:
    root: Path
    python_executable: Path
    identity: PythonAbiIdentity


def platform_key() -> str:
    machine = platform.machine().lower()
    if machine in {"amd64", "x86_64"}:
        architecture = "x86_64"
    else:
        raise PythonToolchainError(
            f"unsupported Python toolchain architecture: {machine}"
        )
    if sys.platform.startswith("linux"):
        operating_system = "linux"
    elif sys.platform == "win32":
        operating_system = "windows"
    else:
        raise PythonToolchainError(
            f"unsupported Python toolchain platform: {sys.platform}"
        )
    return f"{operating_system}-{architecture}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_root(repo_root: Path) -> Path:
    return Path(
        os.environ.get(
            "TERMIN_PYTHON_TOOLCHAIN_BUILD_DIR",
            str(repo_root / "build" / "python-toolchain"),
        )
    ).resolve()


def _download_artifact(
    artifact: PythonToolchainArtifact,
    downloads: Path,
) -> Path:
    downloads.mkdir(parents=True, exist_ok=True)
    destination = downloads / artifact.filename
    if destination.is_file():
        actual = _sha256(destination)
        if actual != artifact.sha256:
            raise PythonToolchainError(
                f"cached Python toolchain artifact hash mismatch: {destination}; "
                f"expected {artifact.sha256}, got {actual}"
            )
        print(f"Using cached Python toolchain artifact: {destination}")
        return destination
    if os.environ.get("TERMIN_PYTHON_TOOLCHAIN_OFFLINE") == "1":
        raise PythonToolchainError(
            f"offline Python toolchain artifact is missing: {destination}"
        )
    print(f"Downloading pinned Python toolchain: {artifact.url}")
    temporary = downloads / f".{artifact.filename}.{os.getpid()}.tmp"
    try:
        with urlopen(artifact.url) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        actual = _sha256(temporary)
        if actual != artifact.sha256:
            raise PythonToolchainError(
                f"downloaded Python toolchain hash mismatch: expected "
                f"{artifact.sha256}, got {actual}"
            )
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def _safe_archive_path(name: str, *, context: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise PythonToolchainError(f"{context} escapes extraction root: {name}")
    return path


def _extract_tar(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:*") as source:
        members = source.getmembers()
        for member in members:
            member_path = _safe_archive_path(
                member.name,
                context="Python source archive member",
            )
            if member.issym() or member.islnk():
                link_path = PurePosixPath(member.linkname)
                if link_path.is_absolute():
                    raise PythonToolchainError(
                        f"Python source archive link is absolute: {member.name}"
                    )
                combined = member_path.parent.joinpath(link_path)
                if ".." in combined.parts:
                    raise PythonToolchainError(
                        f"Python source archive link escapes root: {member.name}"
                    )
        source.extractall(destination)


def _extract_zip(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as source:
        for name in source.namelist():
            _safe_archive_path(name, context="Python NuGet member")
        source.extractall(destination)


def _sanitized_build_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONUSERBASE",
        "CFLAGS",
        "CPPFLAGS",
        "LDFLAGS",
    ):
        environment.pop(name, None)
    environment["CFLAGS"] = "-O2"
    # GNU ld consumes LD_RUN_PATH directly. Passing $ORIGIN through configure,
    # Make, and a recipe shell loses one level of escaping and can silently
    # produce a broken "RIGIN/../lib" RUNPATH.
    environment["LD_RUN_PATH"] = "$ORIGIN/../lib"
    return environment


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    print("+ " + " ".join(command))
    result = subprocess.run(command, cwd=cwd, env=env, check=False)
    if result.returncode != 0:
        raise PythonToolchainError(
            f"Python toolchain command failed with exit code "
            f"{result.returncode}: {' '.join(command)}"
        )


def _cache_fingerprint(
    lock: PythonToolchainLock,
    artifact: PythonToolchainArtifact,
    key: str,
) -> str:
    value = {
        "schema": SCHEMA_VERSION,
        "build_recipe": BUILD_RECIPE_VERSION,
        "version": lock.version,
        "platform": key,
        "artifact": artifact.to_dict(),
    }
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:20]


def _build_linux_runtime(
    lock: PythonToolchainLock,
    artifact: PythonToolchainArtifact,
    key: str,
    archive: Path,
    cache_root: Path,
) -> Path:
    fingerprint = _cache_fingerprint(lock, artifact, key)
    runtime_root = cache_root / "runtimes" / f"cpython-{lock.version}t-{fingerprint}"
    if runtime_root.is_dir():
        return runtime_root
    runtime_root.parent.mkdir(parents=True, exist_ok=True)
    work_parent = cache_root / "work"
    work_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"cpython-{lock.version}t-",
        dir=work_parent,
    ) as temporary:
        work_root = Path(temporary)
        source_parent = work_root / "source"
        source_parent.mkdir()
        _extract_tar(archive, source_parent)
        source_root = source_parent / str(artifact.archive_root)
        configure = source_root / "configure"
        if not configure.is_file():
            raise PythonToolchainError(
                f"Python source configure script is missing: {configure}"
            )
        build_root = work_root / "build"
        build_root.mkdir()
        staging_root = work_root / "install-root"
        environment = _sanitized_build_environment()
        _run(
            [
                str(configure),
                f"--prefix={runtime_root}",
                *artifact.configure_args,
            ],
            cwd=build_root,
            env=environment,
        )
        _run(
            ["make", "-j", str(max(1, os.cpu_count() or 1))],
            cwd=build_root,
            env=environment,
        )
        _run(
            ["make", "install", f"DESTDIR={staging_root}"],
            cwd=build_root,
            env=environment,
        )
        staged_runtime = staging_root / runtime_root.relative_to(runtime_root.anchor)
        if not staged_runtime.is_dir():
            raise PythonToolchainError(
                f"staged Python runtime is missing: {staged_runtime}"
            )
        staged_runtime.replace(runtime_root)
    return runtime_root


def _install_windows_runtime(
    lock: PythonToolchainLock,
    artifact: PythonToolchainArtifact,
    key: str,
    archive: Path,
    cache_root: Path,
) -> Path:
    fingerprint = _cache_fingerprint(lock, artifact, key)
    runtime_root = cache_root / "runtimes" / f"cpython-{lock.version}t-{fingerprint}"
    if runtime_root.is_dir():
        return runtime_root
    runtime_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f"cpython-{lock.version}t-",
            dir=runtime_root.parent,
        )
    )
    try:
        _extract_zip(archive, staging)
        staging.replace(runtime_root)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return runtime_root


def _python_executable(
    runtime_root: Path,
    artifact: PythonToolchainArtifact,
) -> Path:
    if artifact.kind == "nuget":
        candidate = runtime_root / str(artifact.runtime_root) / "python.exe"
        if candidate.is_file():
            return candidate
    else:
        for name in ("python3.14t", "python3.14", "python3"):
            candidate = runtime_root / "bin" / name
            if candidate.is_file():
                return candidate
    raise PythonToolchainError(
        f"pinned Python executable was not found under {runtime_root}"
    )


def _probe_identity(python_executable: Path) -> tuple[PythonAbiIdentity, bool, str]:
    script = (
        "import json, sys, sysconfig; "
        "print(json.dumps({"
        "'version': f'{sys.version_info.major}.{sys.version_info.minor}', "
        "'soabi': sysconfig.get_config_var('SOABI') or '', "
        "'free_threaded': bool(sysconfig.get_config_var('Py_GIL_DISABLED') or 0), "
        "'py_gil_disabled': bool(sysconfig.get_config_var('Py_GIL_DISABLED') or 0), "
        "'gil_enabled': sys._is_gil_enabled(), "
        "'abiflags': sys.abiflags"
        "}))"
    )
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONUSERBASE", None)
    environment["PYTHON_GIL"] = "0"
    result = subprocess.run(
        [str(python_executable), "-I", "-c", script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    if result.returncode != 0:
        detail = result.stderr.strip()
        raise PythonToolchainError(
            f"failed to inspect pinned Python {python_executable}: {detail}"
        )
    try:
        value = json.loads(result.stdout)
        identity = PythonAbiIdentity.from_runtime_probe(
            value,
            context="pinned Python toolchain",
        )
    except (json.JSONDecodeError, PythonAbiError) as error:
        raise PythonToolchainError(
            f"invalid pinned Python identity from {python_executable}: {error}"
        ) from error
    return identity, bool(value.get("gil_enabled")), str(value.get("abiflags", ""))


def ensure_python_toolchain(repo_root: Path) -> PythonToolchain:
    lock_path = repo_root / LOCK_RELATIVE_PATH
    lock = PythonToolchainLock.load(lock_path)
    key = platform_key()
    artifact = lock.platforms.get(key)
    if artifact is None:
        raise PythonToolchainError(
            f"Python toolchain lock has no artifact for {key}"
        )
    cache_root = _cache_root(repo_root)
    archive = _download_artifact(artifact, cache_root / "downloads")
    if artifact.kind == "source":
        runtime_root = _build_linux_runtime(
            lock,
            artifact,
            key,
            archive,
            cache_root,
        )
    else:
        runtime_root = _install_windows_runtime(
            lock,
            artifact,
            key,
            archive,
            cache_root,
        )
    python_executable = _python_executable(runtime_root, artifact)
    identity, gil_enabled, abiflags = _probe_identity(python_executable)
    if identity.version != lock.abi_version:
        raise PythonToolchainError(
            f"pinned Python version mismatch: expected {lock.abi_version}, "
            f"got {identity.version}"
        )
    if not identity.free_threaded or not identity.py_gil_disabled:
        raise PythonToolchainError(
            f"pinned Python is not free-threaded: {identity.canonical_json()}"
        )
    if gil_enabled:
        raise PythonToolchainError(
            "pinned Python started with the GIL enabled"
        )
    if "t" not in abiflags:
        raise PythonToolchainError(
            f"pinned Python abiflags do not contain 't': {abiflags!r}"
        )
    manifest = {
        "schema": SCHEMA_VERSION,
        "version": lock.version,
        "platform": key,
        "artifact": artifact.to_dict(),
        "python_abi": identity.to_dict(),
        "python_executable": str(python_executable.relative_to(runtime_root)),
    }
    (runtime_root / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Pinned Python toolchain ready: {python_executable} "
        f"({identity.soabi}, GIL disabled)"
    )
    return PythonToolchain(
        root=runtime_root,
        python_executable=python_executable,
        identity=identity,
    )
