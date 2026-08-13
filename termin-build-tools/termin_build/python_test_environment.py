"""Prepare and validate the checkout-local Python test tool environment."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .python_abi import PythonAbiError, PythonAbiIdentity


MANIFEST_NAME = "test-environment.json"
LEGACY_REQUIREMENTS_STAMP_NAME = "python-test-requirements.txt"
SCHEMA_VERSION = 1
SITE_PACKAGES_NAME = "site-packages"
_EXACT_REQUIREMENT_RE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==([^\s;]+)$"
)
_DISTRIBUTION_NORMALIZE_RE = re.compile(r"[-_.]+")


class PythonTestEnvironmentError(RuntimeError):
    """Raised when the test tool environment is stale or cannot be prepared."""


@dataclass(frozen=True)
class RuntimeIdentity:
    python_abi: PythonAbiIdentity
    platform: str
    machine: str

    @classmethod
    def current(cls) -> "RuntimeIdentity":
        return cls(
            python_abi=PythonAbiIdentity.current(),
            platform=sys.platform,
            machine=platform.machine().lower(),
        )

    @classmethod
    def from_mapping(
        cls,
        value: object,
        *,
        context: str,
    ) -> "RuntimeIdentity":
        if not isinstance(value, Mapping):
            raise PythonTestEnvironmentError(f"{context} must be an object")
        runtime_platform = value.get("platform")
        machine = value.get("machine")
        if not isinstance(runtime_platform, str) or not runtime_platform:
            raise PythonTestEnvironmentError(f"{context}.platform must be a string")
        if not isinstance(machine, str) or not machine:
            raise PythonTestEnvironmentError(f"{context}.machine must be a string")
        try:
            python_abi = PythonAbiIdentity.from_mapping(
                value.get("python_abi"),
                context=f"{context}.python_abi",
            )
        except PythonAbiError as error:
            raise PythonTestEnvironmentError(str(error)) from error
        return cls(
            python_abi=python_abi,
            platform=runtime_platform,
            machine=machine.lower(),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "python_abi": self.python_abi.to_dict(),
            "platform": self.platform,
            "machine": self.machine,
        }

    def require_matches(
        self,
        actual: "RuntimeIdentity",
        *,
        context: str,
    ) -> None:
        if self != actual:
            raise PythonTestEnvironmentError(
                f"{context} mismatch: expected "
                f"{json.dumps(self.to_dict(), sort_keys=True)}, got "
                f"{json.dumps(actual.to_dict(), sort_keys=True)}"
            )


def _normalized_distribution_name(name: str) -> str:
    return _DISTRIBUTION_NORMALIZE_RE.sub("-", name).lower()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _locked_requirements(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.partition("#")[0].strip()
        if not line:
            continue
        match = _EXACT_REQUIREMENT_RE.fullmatch(line)
        if match is None:
            raise PythonTestEnvironmentError(
                f"test requirement must be an exact name==version pin at "
                f"{path}:{line_number}: {raw_line!r}"
            )
        name = _normalized_distribution_name(match.group(1))
        if name in result:
            raise PythonTestEnvironmentError(
                f"duplicate test requirement {name!r} in {path}"
            )
        result[name] = match.group(2)
    if not result:
        raise PythonTestEnvironmentError(f"test requirements are empty: {path}")
    return dict(sorted(result.items()))


def _installed_distributions(site_packages: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    duplicates: set[str] = set()
    for distribution in importlib.metadata.distributions(path=[str(site_packages)]):
        raw_name = distribution.metadata.get("Name")
        if not raw_name:
            continue
        name = _normalized_distribution_name(raw_name)
        if name in result:
            duplicates.add(name)
        result[name] = distribution.version
    if duplicates:
        rendered = ", ".join(sorted(duplicates))
        raise PythonTestEnvironmentError(
            f"test environment contains duplicate distributions: {rendered}"
        )
    return dict(sorted(result.items()))


def _expected_manifest(
    requirements: Path,
    identity: RuntimeIdentity,
) -> dict[str, object]:
    return {
        "schema": SCHEMA_VERSION,
        "runtime": identity.to_dict(),
        "requirements_sha256": _sha256(requirements),
        "distributions": _locked_requirements(requirements),
    }


def _read_manifest(path: Path) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PythonTestEnvironmentError(
            f"failed to read Python test environment manifest {path}: {error}"
        ) from error
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA_VERSION:
        raise PythonTestEnvironmentError(
            f"unsupported Python test environment manifest: {path}"
        )
    return raw


def validate_test_environment(
    environment_root: Path,
    requirements: Path,
    *,
    identity: RuntimeIdentity | None = None,
) -> dict[str, object]:
    environment_root = environment_root.resolve()
    requirements = requirements.resolve()
    manifest_path = environment_root / MANIFEST_NAME
    site_packages = environment_root / SITE_PACKAGES_NAME
    if not site_packages.is_dir():
        raise PythonTestEnvironmentError(
            f"Python test environment packages are missing: {site_packages}"
        )

    actual_identity = identity or RuntimeIdentity.current()
    expected = _expected_manifest(requirements, actual_identity)
    manifest = _read_manifest(manifest_path)
    try:
        recorded_identity = RuntimeIdentity.from_mapping(
            manifest.get("runtime"),
            context=f"Python test environment {manifest_path} runtime",
        )
        recorded_identity.require_matches(
            actual_identity,
            context="Python test environment runtime",
        )
    except PythonTestEnvironmentError:
        raise

    if manifest.get("requirements_sha256") != expected["requirements_sha256"]:
        raise PythonTestEnvironmentError(
            "Python test requirements changed since the environment was prepared"
        )
    if manifest.get("distributions") != expected["distributions"]:
        raise PythonTestEnvironmentError(
            f"Python test environment manifest has unexpected distributions: "
            f"{manifest_path}"
        )
    installed = _installed_distributions(site_packages)
    if installed != expected["distributions"]:
        raise PythonTestEnvironmentError(
            "Python test environment contents do not match the exact test lock: "
            f"expected {expected['distributions']}, got {installed}"
        )
    return manifest


_RUNTIME_PROBE = (
    "import json, platform, sys, sysconfig; "
    "gil=bool(sysconfig.get_config_var('Py_GIL_DISABLED') or 0); "
    "print(json.dumps({'python_abi': {"
    "'version': f'{sys.version_info.major}.{sys.version_info.minor}', "
    "'soabi': sysconfig.get_config_var('SOABI') or '', "
    "'free_threaded': gil, 'py_gil_disabled': gil}, "
    "'platform': sys.platform, 'machine': platform.machine().lower()}))"
)


def probe_runtime_identity(python_executable: Path) -> RuntimeIdentity:
    result = subprocess.run(
        [str(python_executable), "-I", "-c", _RUNTIME_PROBE],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise PythonTestEnvironmentError(
            f"failed to inspect test tool installer {python_executable}: {detail}"
        )
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise PythonTestEnvironmentError(
            f"test tool installer returned invalid runtime identity: "
            f"{python_executable}"
        ) from error
    return RuntimeIdentity.from_mapping(
        raw,
        context=f"test tool installer {python_executable}",
    )


def _install_requirements(
    installer_python: Path,
    requirements: Path,
    target: Path,
) -> None:
    result = subprocess.run(
        [
            str(installer_python),
            "-I",
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--ignore-installed",
            "--upgrade",
            "--target",
            str(target),
            "-r",
            str(requirements),
        ],
        check=False,
    )
    if result.returncode != 0:
        raise PythonTestEnvironmentError(
            f"test tool installation failed with exit code {result.returncode}"
        )


def _write_json_atomic(path: Path, data: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _replace_site_packages(
    environment_root: Path,
    prepared: Path,
    manifest: dict[str, object],
) -> None:
    site_packages = environment_root / SITE_PACKAGES_NAME
    manifest_path = environment_root / MANIFEST_NAME
    backup = environment_root / f".{SITE_PACKAGES_NAME}.{uuid.uuid4().hex}.old"
    had_previous = site_packages.exists()
    if had_previous:
        site_packages.replace(backup)
    try:
        prepared.replace(site_packages)
        _write_json_atomic(manifest_path, manifest)
    except BaseException:
        if site_packages.exists():
            shutil.rmtree(site_packages)
        if had_previous and backup.exists():
            backup.replace(site_packages)
        raise
    finally:
        if backup.exists():
            shutil.rmtree(backup)


def prepare_test_environment(
    environment_root: Path,
    requirements: Path,
    installer_python: Path,
    *,
    force: bool = False,
    install: Callable[[Path, Path, Path], None] = _install_requirements,
) -> bool:
    environment_root = environment_root.resolve()
    requirements = requirements.resolve()
    installer_python = installer_python.resolve()
    environment_root.mkdir(parents=True, exist_ok=True)

    sdk_identity = RuntimeIdentity.current()
    installer_identity = probe_runtime_identity(installer_python)
    sdk_identity.require_matches(
        installer_identity,
        context="SDK Python and test tool installer runtime",
    )
    expected_manifest = _expected_manifest(requirements, sdk_identity)
    legacy_stamp = environment_root / LEGACY_REQUIREMENTS_STAMP_NAME

    if not force:
        try:
            validate_test_environment(
                environment_root,
                requirements,
                identity=sdk_identity,
            )
        except PythonTestEnvironmentError:
            pass
        else:
            legacy_stamp.unlink(missing_ok=True)
            return False

    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{SITE_PACKAGES_NAME}.",
            suffix=".tmp",
            dir=environment_root,
        )
    )
    try:
        install(installer_python, requirements, temporary)
        installed = _installed_distributions(temporary)
        if installed != expected_manifest["distributions"]:
            raise PythonTestEnvironmentError(
                "installed test tool contents do not match the exact test lock: "
                f"expected {expected_manifest['distributions']}, got {installed}"
            )
        _replace_site_packages(environment_root, temporary, expected_manifest)
        legacy_stamp.unlink(missing_ok=True)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--environment-root", type=Path, required=True)
    prepare.add_argument("--requirements", type=Path, required=True)
    prepare.add_argument("--installer-python", type=Path, required=True)
    prepare.add_argument("--force", action="store_true")

    validate = subparsers.add_parser("validate")
    validate.add_argument("--environment-root", type=Path, required=True)
    validate.add_argument("--requirements", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "prepare":
            rebuilt = prepare_test_environment(
                args.environment_root,
                args.requirements,
                args.installer_python,
                force=args.force,
            )
            if rebuilt:
                print(
                    "Installed clean test-only tools into: "
                    f"{args.environment_root / SITE_PACKAGES_NAME}"
                )
            else:
                print(
                    "Test-only tools are up to date: "
                    f"{args.environment_root / SITE_PACKAGES_NAME}"
                )
        else:
            validate_test_environment(args.environment_root, args.requirements)
    except PythonTestEnvironmentError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        if args.command == "validate":
            print(
                "Run scripts/test/setup-python-env.sh "
                "(or scripts\\test\\setup-python-env.ps1 on Windows) to rebuild it.",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
