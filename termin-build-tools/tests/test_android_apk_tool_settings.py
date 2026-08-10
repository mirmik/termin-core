from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="exercises the POSIX build-android-apk.sh wrapper"
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _executable(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_android_apk_wrapper_uses_shared_toolchain_settings(tmp_path: Path) -> None:
    termin_root = tmp_path / "termin"
    (termin_root / "build-system").mkdir(parents=True)
    (termin_root / "termin-android/platform").mkdir(parents=True)
    (termin_root / "termin-android/assets").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "build-android-apk.sh", termin_root / "build-android-apk.sh")
    shutil.copy2(
        REPO_ROOT / "build-system/read-termin-user-setting.py",
        termin_root / "build-system/read-termin-user-setting.py",
    )

    fake_python = _executable(
        tmp_path / "fake-python",
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-m\" ]; then\n"
        "  shift 2\n"
        "  while [ \"$#\" -gt 0 ]; do\n"
        "    if [ \"$1\" = \"--output\" ]; then shift; mkdir -p \"$1\"; fi\n"
        "    shift\n"
        "  done\n"
        "  exit 0\n"
        "fi\n"
        f'exec "{sys.executable}" "$@"\n',
    )
    gradle_log = tmp_path / "gradle.log"
    fake_gradle = _executable(
        tmp_path / "gradle/bin/gradle",
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then echo 'Gradle 8.14.5'; exit 0; fi\n"
        "printf '%s\\n%s\\n%s\\n' \"$ANDROID_HOME\" \"$JAVA_HOME\" \"$*\" > \"$FAKE_GRADLE_LOG\"\n",
    )
    android_home = tmp_path / "google-android-sdk"
    (android_home / "platforms").mkdir(parents=True)
    ndk_root = tmp_path / "google-android-sdk/ndk/27.2.12479018"
    (ndk_root / "build/cmake").mkdir(parents=True)
    (ndk_root / "build/cmake/android.toolchain.cmake").write_text("# fake\n", encoding="utf-8")
    java_home = tmp_path / "jdk"
    _executable(java_home / "bin/java", "#!/bin/sh\nexit 0\n")
    termin_android_sdk = tmp_path / "termin-android-sdk"
    termin_android_sdk.mkdir()

    config_home = tmp_path / "config"
    settings = config_home / "termin/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        json.dumps(
            {
                "Build": {
                    "androidSdkRoot": str(termin_android_sdk),
                    "androidHome": str(android_home),
                    "androidNdkRoot": str(ndk_root),
                    "javaHome": str(java_home),
                    "gradle": str(fake_gradle),
                    "shaderCompiler": str(tmp_path / "termin_shaderc"),
                }
            }
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    for name in (
        "ANDROID_HOME",
        "ANDROID_SDK_ROOT",
        "ANDROID_NDK_HOME",
        "ANDROID_NDK_ROOT",
        "JAVA_HOME",
        "GRADLE_BIN",
        "TERMIN_ANDROID_SDK_ROOT",
        "TERMIN_SHADERC",
    ):
        env.pop(name, None)
    env["XDG_CONFIG_HOME"] = str(config_home)
    env["TERMIN_HOST_PYTHON"] = str(fake_python)
    env["FAKE_GRADLE_LOG"] = str(gradle_log)

    result = subprocess.run(
        [str(termin_root / "build-android-apk.sh")],
        cwd=termin_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert f"Gradle:          {fake_gradle}" in result.stdout
    assert f"Termin SDK root: {termin_android_sdk}" in result.stdout
    assert f"Android SDK:      {android_home}" in result.stdout
    assert f"Android NDK:      {ndk_root}" in result.stdout
    assert f"Java home:        {java_home}" in result.stdout
    log_lines = gradle_log.read_text(encoding="utf-8").splitlines()
    assert log_lines[0] == str(android_home)
    assert log_lines[1] == str(java_home)
    assert f"-PterminAndroidNdkRoot={ndk_root}" in log_lines[2]

    environment_android_home = tmp_path / "environment-android-sdk"
    (environment_android_home / "platforms").mkdir(parents=True)
    environment_ndk = environment_android_home / "ndk/current"
    (environment_ndk / "build/cmake").mkdir(parents=True)
    (environment_ndk / "build/cmake/android.toolchain.cmake").write_text(
        "# fake\n", encoding="utf-8"
    )
    environment_java = tmp_path / "environment-jdk"
    _executable(environment_java / "bin/java", "#!/bin/sh\nexit 0\n")
    environment_sdk = tmp_path / "environment-termin-android-sdk"
    environment_sdk.mkdir()
    environment_gradle = _executable(
        tmp_path / "environment-gradle/bin/gradle",
        fake_gradle.read_text(encoding="utf-8"),
    )
    env.update(
        {
            "ANDROID_HOME": str(environment_android_home),
            "ANDROID_NDK_HOME": str(environment_ndk),
            "JAVA_HOME": str(environment_java),
            "GRADLE_BIN": str(environment_gradle),
            "TERMIN_ANDROID_SDK_ROOT": str(environment_sdk),
        }
    )

    environment_result = subprocess.run(
        [str(termin_root / "build-android-apk.sh")],
        cwd=termin_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert environment_result.returncode == 0, environment_result.stderr
    assert f"Gradle:          {environment_gradle}" in environment_result.stdout
    assert f"Termin SDK root: {environment_sdk}" in environment_result.stdout
    assert f"Android SDK:      {environment_android_home}" in environment_result.stdout
    assert f"Android NDK:      {environment_ndk}" in environment_result.stdout
    assert f"Java home:        {environment_java}" in environment_result.stdout
