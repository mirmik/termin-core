from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest


pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="exercises the POSIX build-sdk-android.sh wrapper"
)


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = REPO_ROOT / "build-sdk-android.sh"


def _ndk(root: Path, name: str) -> Path:
    ndk = root / name
    toolchain = ndk / "build/cmake/android.toolchain.cmake"
    toolchain.parent.mkdir(parents=True)
    toolchain.write_text("# test toolchain\n", encoding="utf-8")
    return ndk


def _fake_cmake(root: Path) -> Path:
    executable = root / "bin/cmake"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    return executable.parent


def _run_script(
    tmp_path: Path,
    *,
    configured_ndk: Path,
    environment_ndk: Path | None = None,
    environment_variable: str = "ANDROID_NDK_HOME",
    explicit_ndk: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    config_home = tmp_path / "config"
    settings = config_home / "termin/settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(
        json.dumps({"Build": {"androidNdkRoot": str(configured_ndk)}}),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.pop("ANDROID_NDK_HOME", None)
    env.pop("ANDROID_NDK_ROOT", None)
    env["XDG_CONFIG_HOME"] = str(config_home)
    env["PATH"] = f"{_fake_cmake(tmp_path)}{os.pathsep}{env['PATH']}"
    if environment_ndk is not None:
        env[environment_variable] = str(environment_ndk)
    command = [
        str(BUILD_SCRIPT),
        "--no-install",
        "--build-dir",
        str(tmp_path / "build"),
        "--prefix",
        str(tmp_path / "sdk"),
    ]
    if explicit_ndk is not None:
        command.extend(("--ndk", str(explicit_ndk)))
    return subprocess.run(command, env=env, text=True, capture_output=True, check=False)


def test_android_sdk_build_uses_ndk_from_termin_user_settings(tmp_path: Path) -> None:
    configured = _ndk(tmp_path, "configured-ndk")

    result = _run_script(tmp_path, configured_ndk=configured)

    assert result.returncode == 0, result.stderr
    assert f"NDK:              {configured}" in result.stdout


def test_android_sdk_build_ndk_precedence_is_argument_environment_settings(
    tmp_path: Path,
) -> None:
    configured = _ndk(tmp_path, "configured-ndk")
    environment = _ndk(tmp_path, "environment-ndk")
    explicit = _ndk(tmp_path, "explicit-ndk")

    from_environment = _run_script(
        tmp_path,
        configured_ndk=configured,
        environment_ndk=environment,
    )
    from_legacy_environment = _run_script(
        tmp_path,
        configured_ndk=configured,
        environment_ndk=environment,
        environment_variable="ANDROID_NDK_ROOT",
    )
    from_argument = _run_script(
        tmp_path,
        configured_ndk=configured,
        environment_ndk=environment,
        explicit_ndk=explicit,
    )

    assert from_environment.returncode == 0, from_environment.stderr
    assert f"NDK:              {environment}" in from_environment.stdout
    assert from_legacy_environment.returncode == 0, from_legacy_environment.stderr
    assert f"NDK:              {environment}" in from_legacy_environment.stdout
    assert from_argument.returncode == 0, from_argument.stderr
    assert f"NDK:              {explicit}" in from_argument.stdout
