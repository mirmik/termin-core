import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

from termin_build import (
    artifact_manifest,
    sdk,
    sdk_bundled_python,
    sdk_verification,
)
from termin_build.package_manifest import NativeExtension, PackageEntry
from termin_build.sdk_doctor import PROFILES


@pytest.mark.parametrize("profile_name", ["sdk", "sdk-cpp", "sdk-bindings", "cpp-tests"])
def test_native_build_profiles_require_eigen(profile_name):
    assert "termin-thirdparty/eigen" in PROFILES[profile_name].submodules


def test_sdk_doctor_profile_checks_copy_backend(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sdk, "_is_windows", lambda: False)
    monkeypatch.setattr(
        sdk.shutil,
        "which",
        lambda tool: None if tool == "rsync" else f"/usr/bin/{tool}",
    )
    monkeypatch.setattr(sdk, "_nanobind_error", lambda: None)
    monkeypatch.setattr(sdk, "_pip_error", lambda: None)
    monkeypatch.setattr(sdk, "_pip_cache_warning", lambda: None)
    monkeypatch.setattr(sdk, "missing_submodules", lambda _repo_root, _paths: [])

    result = sdk.doctor(
        repo_root=tmp_path,
        profile_name="sdk",
        vulkan="OFF",
        init_submodules=False,
        require_nanobind=False,
        sdk_prefix=tmp_path / "sdk",
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "required copy backend not found in PATH: rsync" in captured.err


def test_sdk_doctor_profile_checks_pip(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sdk, "_is_windows", lambda: True)
    monkeypatch.setattr(sdk.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(sdk, "_nanobind_error", lambda: None)
    monkeypatch.setattr(sdk, "_pip_error", lambda: "pip is not available")
    monkeypatch.setattr(sdk, "_pip_cache_warning", lambda: None)
    monkeypatch.setattr(sdk, "missing_submodules", lambda _repo_root, _paths: [])

    result = sdk.doctor(
        repo_root=tmp_path,
        profile_name="sdk",
        vulkan="OFF",
        init_submodules=False,
        require_nanobind=False,
        sdk_prefix=tmp_path / "sdk",
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "pip is not available" in captured.err


def test_write_artifacts_records_install_path_and_runtime_dependencies(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    build_dir = tmp_path / "build"
    sdk_prefix = tmp_path / "sdk"
    install_dir = sdk_prefix
    build_bin = build_dir / "bin"
    install_pkg = install_dir / "lib" / "python" / "termin" / "sample"
    build_bin.mkdir(parents=True)
    install_pkg.mkdir(parents=True)

    build_artifact = (
        build_bin
        / f"_sample_native.{artifact_manifest.PythonAbiIdentity.current().soabi}.so"
    )
    install_artifact = install_pkg / build_artifact.name
    build_artifact.write_text("native", encoding="utf-8")
    install_artifact.write_text("native", encoding="utf-8")
    runtime_library = sdk_prefix / "lib" / "libtermin_sample.so"
    runtime_library.parent.mkdir(parents=True, exist_ok=True)
    runtime_library.write_text("runtime", encoding="utf-8")

    packages = [
        PackageEntry(
            path="termin-sample",
            distribution="termin-sample",
            features=(),
            native_extensions=(
                NativeExtension(
                    extension="termin.sample._sample_native",
                    target="_sample_native",
                    optional=False,
                    features=("sample",),
                ),
            ),
        )
    ]
    monkeypatch.setattr(sdk, "load_manifest", lambda _repo_root: packages)
    monkeypatch.setattr(
        sdk,
        "_native_runtime_dependencies",
        lambda _binary: ["libtermin_sample.so"],
    )

    result = sdk.write_artifacts(
        repo_root=repo_root,
        build_dir=build_dir,
        sdk_prefix=sdk_prefix,
        install_dir=install_dir,
    )

    assert result == 0
    data = json.loads((sdk_prefix / "termin-artifacts.json").read_text())
    assert data["schema"] == artifact_manifest.SCHEMA_VERSION
    assert data["manifest_kind"] == "termin-sdk-artifacts"
    assert data["python_abi"] == artifact_manifest.PythonAbiIdentity.current().to_dict()
    artifact = data["artifacts"][0]
    assert artifact["path"] == install_artifact.relative_to(sdk_prefix).as_posix()
    assert artifact["sha256"] == hashlib.sha256(b"native").hexdigest()
    assert artifact["runtime_dependencies"] == [
        {
            "name": "libtermin_sample.so",
            "path": "lib/libtermin_sample.so",
            "sha256": hashlib.sha256(b"runtime").hexdigest(),
        }
    ]
    assert artifact["features"] == ["sample"]
    capabilities = json.loads(
        (sdk_prefix / "termin-sdk-capabilities.json").read_text(encoding="utf-8")
    )
    assert capabilities["platforms"]["desktop"]["os"] == (
        "windows" if sys.platform == "win32" else "linux"
    )
    assert capabilities["platforms"]["desktop"]["arch"] == "x86_64"
    build_data = json.loads(
        (build_dir / "termin-build-artifacts.json").read_text()
    )
    assert build_data["manifest_kind"] == "termin-build-artifacts"
    assert build_data["artifacts"][0]["path"] == str(build_artifact.resolve())


def test_native_runtime_dependencies_are_locale_independent(monkeypatch):
    captured_env = {}

    def run(command, **kwargs):
        captured_env.update(kwargs["env"])
        return sdk.subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                " 0x0000000000000001 (NEEDED)             "
                "Совм. исп. библиотека: [libnanobind-ft.so]\n"
                " 0x0000000000000001 (NEEDED)             "
                "Совм. исп. библиотека: [libc.so.6]\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(sdk, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk.subprocess, "run", run)

    dependencies = sdk._native_runtime_dependencies(Path("extension.so"))

    assert dependencies == ["libnanobind-ft.so", "libc.so.6"]
    assert captured_env["LC_ALL"] == "C"
    assert captured_env["LANGUAGE"] == "C"


def test_pe_import_dependencies_reads_windows_import_table(tmp_path):
    image = bytearray(0x400)
    image[:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"
    file_header = 0x84
    struct.pack_into("<H", image, file_header + 2, 1)
    struct.pack_into("<H", image, file_header + 16, 240)
    optional = file_header + 20
    struct.pack_into("<H", image, optional, 0x20B)
    struct.pack_into("<II", image, optional + 112 + 8, 0x1000, 40)
    section = optional + 240
    struct.pack_into("<IIII", image, section + 8, 0x200, 0x1000, 0x200, 0x200)
    struct.pack_into("<IIIII", image, 0x200, 0, 0, 0, 0x1080, 0)
    image[0x280:0x290] = b"nanobind-ft.dll\0"
    binary = tmp_path / "extension.pyd"
    binary.write_bytes(image)

    assert sdk._pe_import_dependencies(binary) == ["nanobind-ft.dll"]


def test_pe_import_dependencies_rejects_non_pe_file(tmp_path):
    binary = tmp_path / "extension.pyd"
    binary.write_bytes(b"not a PE image")

    with pytest.raises(RuntimeError, match="missing DOS header"):
        sdk._pe_import_dependencies(binary)


def test_native_runtime_dependencies_reports_readelf_failure(monkeypatch):
    def run(command, **_kwargs):
        return sdk.subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="readelf: Error: Not an ELF file",
        )

    monkeypatch.setattr(sdk, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk.subprocess, "run", run)

    with pytest.raises(RuntimeError, match="Not an ELF file"):
        sdk._native_runtime_dependencies(Path("extension.so"))


def test_write_artifacts_reports_missing_required_binding(
    tmp_path,
    monkeypatch,
    capsys,
):
    packages = [
        PackageEntry(
            path="termin-navmesh",
            distribution="termin-navmesh",
            features=("recast",),
            native_extensions=(
                NativeExtension(
                    extension="termin.navmesh._navmesh_native",
                    target="_navmesh_native",
                    optional=False,
                    features=("recast",),
                ),
            ),
        )
    ]
    monkeypatch.setattr(sdk, "load_manifest", lambda _repo_root: packages)

    result = sdk.write_artifacts(
        repo_root=tmp_path,
        build_dir=tmp_path / "build",
        sdk_prefix=tmp_path / "sdk",
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "required native artifacts are missing" in captured.err
    assert "termin.navmesh._navmesh_native" in captured.err


def test_write_artifacts_supports_windows_pyd_layout(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    build_dir = tmp_path / "build"
    sdk_prefix = tmp_path / "sdk"
    build_bin = build_dir / "bin" / "Release"
    install_pkg = sdk_prefix / "python" / "Lib" / "site-packages" / "termin" / "navmesh"
    build_bin.mkdir(parents=True)
    install_pkg.mkdir(parents=True)

    build_artifact = build_bin / "_navmesh_native.cp310-win_amd64.pyd"
    install_artifact = install_pkg / build_artifact.name
    build_artifact.write_text("native", encoding="utf-8")
    install_artifact.write_text("native", encoding="utf-8")

    packages = [
        PackageEntry(
            path="termin-navmesh",
            distribution="termin-navmesh",
            features=("recast",),
            native_extensions=(
                NativeExtension(
                    extension="termin.navmesh._navmesh_native",
                    target="_navmesh_native",
                    optional=False,
                    features=("recast",),
                ),
            ),
        )
    ]
    monkeypatch.setattr(sdk, "load_manifest", lambda _repo_root: packages)
    monkeypatch.setattr(sdk, "_is_windows", lambda: True)
    monkeypatch.setattr(sdk, "_native_runtime_dependencies", lambda _path: [])
    monkeypatch.setattr(
        sdk.PythonAbiIdentity,
        "current",
        lambda: sdk.PythonAbiIdentity(
            version="3.10",
            soabi="cp310-win_amd64",
            free_threaded=False,
            py_gil_disabled=False,
        ),
    )

    result = sdk.write_artifacts(
        repo_root=repo_root,
        build_dir=build_dir,
        sdk_prefix=sdk_prefix,
    )

    assert result == 0
    data = json.loads((sdk_prefix / "termin-artifacts.json").read_text())
    artifact = data["artifacts"][0]
    assert artifact["path"] == install_artifact.relative_to(sdk_prefix).as_posix()
    assert artifact["runtime_dependencies"] == []


def test_write_artifacts_prefers_windows_config_pyd_over_stale_bin_copy(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    build_dir = tmp_path / "build"
    sdk_prefix = tmp_path / "sdk"
    stale_bin = build_dir / "bin"
    build_bin = stale_bin / "Release"
    install_pkg = sdk_prefix / "python" / "Lib" / "site-packages" / "termin" / "voxels"
    build_bin.mkdir(parents=True)
    install_pkg.mkdir(parents=True)

    stale_artifact = stale_bin / "_voxels_native.cp312-win_amd64.pyd"
    build_artifact = build_bin / "_voxels_native.cp312-win_amd64.pyd"
    install_artifact = install_pkg / build_artifact.name
    stale_artifact.write_text("stale", encoding="utf-8")
    build_artifact.write_text("fresh", encoding="utf-8")
    install_artifact.write_text("fresh", encoding="utf-8")

    packages = [
        PackageEntry(
            path="termin-voxels",
            distribution="termin-voxels",
            features=(),
            native_extensions=(
                NativeExtension(
                    extension="termin.voxels._voxels_native",
                    target="_voxels_native",
                    optional=False,
                    features=(),
                ),
            ),
        )
    ]
    monkeypatch.setattr(sdk, "load_manifest", lambda _repo_root: packages)
    monkeypatch.setattr(sdk, "_is_windows", lambda: True)
    monkeypatch.setattr(sdk, "_native_runtime_dependencies", lambda _path: [])
    monkeypatch.setattr(
        sdk.PythonAbiIdentity,
        "current",
        lambda: sdk.PythonAbiIdentity(
            version="3.12",
            soabi="cp312-win_amd64",
            free_threaded=False,
            py_gil_disabled=False,
        ),
    )

    result = sdk.write_artifacts(
        repo_root=repo_root,
        build_dir=build_dir,
        sdk_prefix=sdk_prefix,
    )

    assert result == 0
    data = json.loads((sdk_prefix / "termin-artifacts.json").read_text())
    artifact = data["artifacts"][0]
    assert artifact["path"] == install_artifact.relative_to(sdk_prefix).as_posix()
    build_data = json.loads(
        (build_dir / "termin-build-artifacts.json").read_text()
    )
    assert build_data["artifacts"][0]["path"] == str(build_artifact.resolve())


def test_write_artifacts_ignores_stale_disabled_feature_extension(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    build_dir = tmp_path / "build"
    sdk_prefix = tmp_path / "sdk"
    build_bin = build_dir / "bin"
    installed = sdk_prefix / "lib" / "python" / "termin" / "display"
    build_bin.mkdir(parents=True)
    installed.mkdir(parents=True)
    (build_dir / "CMakeCache.txt").write_text(
        "TERMIN_ENABLE_SDL:BOOL=OFF\n",
        encoding="utf-8",
    )
    artifact_name = (
        f"_platform_native.{artifact_manifest.PythonAbiIdentity.current().soabi}.so"
    )
    (build_bin / artifact_name).write_text("stale", encoding="utf-8")
    (installed / artifact_name).write_text("stale", encoding="utf-8")

    packages = [
        PackageEntry(
            path="termin-display",
            distribution="termin-display",
            features=(),
            native_extensions=(
                NativeExtension(
                    extension="termin.display._platform_native",
                    target="_platform_native",
                    optional=True,
                    features=("sdl",),
                ),
            ),
        )
    ]
    monkeypatch.setattr(sdk, "load_manifest", lambda _repo_root: packages)

    assert sdk.write_artifacts(repo_root, build_dir, sdk_prefix) == 0
    manifest = json.loads(
        (sdk_prefix / "termin-artifacts.json").read_text(encoding="utf-8")
    )
    assert manifest["artifacts"] == []


def test_verify_duplicate_libraries_reports_windows_duplicates(
    tmp_path,
    monkeypatch,
    capsys,
):
    sdk_prefix = tmp_path / "sdk"
    (sdk_prefix / "bin").mkdir(parents=True)
    (sdk_prefix / "python" / "Lib" / "site-packages").mkdir(parents=True)
    (sdk_prefix / "bin" / "termin_bootstrap.dll").write_text("dll", encoding="utf-8")
    (
        sdk_prefix
        / "python"
        / "Lib"
        / "site-packages"
        / "termin_bootstrap.dll"
    ).write_text("dll", encoding="utf-8")

    monkeypatch.setattr(sdk_verification, "_is_windows", lambda: True)

    result = sdk.verify_no_duplicate_libraries(sdk_prefix)

    captured = capsys.readouterr()
    assert result == 1
    assert "DUPLICATE: termin_bootstrap.dll" in captured.out


def test_verify_duplicate_libraries_ignores_scoped_sdk_duplicates(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    (sdk_prefix / "bin").mkdir(parents=True)
    (sdk_prefix / "android" / "arm64-v8a").mkdir(parents=True)
    (sdk_prefix / "csharp" / "runtimes" / "win-x64" / "native").mkdir(parents=True)
    (sdk_prefix / "bin" / "termin_bootstrap.dll").write_text("dll", encoding="utf-8")
    (sdk_prefix / "android" / "arm64-v8a" / "termin_bootstrap.dll").write_text(
        "dll",
        encoding="utf-8",
    )
    (
        sdk_prefix
        / "csharp"
        / "runtimes"
        / "win-x64"
        / "native"
        / "termin_bootstrap.dll"
    ).write_text("dll", encoding="utf-8")

    monkeypatch.setattr(sdk_verification, "_is_windows", lambda: True)

    assert sdk.verify_no_duplicate_libraries(sdk_prefix) == 0


def test_verify_duplicate_libraries_allows_csharp_tfm_managed_assemblies(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    lib_dir = sdk_prefix / "csharp" / "lib"
    (lib_dir / "netstandard2.1").mkdir(parents=True)
    (lib_dir / "netcoreapp3.1").mkdir(parents=True)
    (lib_dir / "net8.0-windows").mkdir(parents=True)

    (lib_dir / "Termin.Native.dll").write_text("flat-native", encoding="utf-8")
    (lib_dir / "netstandard2.1" / "Termin.Native.dll").write_text(
        "tfm-native",
        encoding="utf-8",
    )
    (lib_dir / "Termin.Wpf.dll").write_text("flat-wpf", encoding="utf-8")
    (lib_dir / "netcoreapp3.1" / "Termin.Wpf.dll").write_text(
        "tfm-wpf-netcore",
        encoding="utf-8",
    )
    (lib_dir / "net8.0-windows" / "Termin.Wpf.dll").write_text(
        "tfm-wpf-net8",
        encoding="utf-8",
    )

    monkeypatch.setattr(sdk_verification, "_is_windows", lambda: True)

    assert sdk.verify_no_duplicate_libraries(sdk_prefix) == 0


def test_windows_python_runtime_copies_cli_and_allows_python_home_dll(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    host_python = tmp_path / "host-python"
    host_python.mkdir()
    (sdk_prefix / "bin").mkdir(parents=True)
    (sdk_prefix / "python").mkdir()
    (sdk_prefix / "bin" / "python312.dll").write_text("stale", encoding="utf-8")
    (sdk_prefix / "python" / "python312.dll").write_text("stale", encoding="utf-8")
    (sdk_prefix / "python" / "python3.12.exe").write_text("stale", encoding="utf-8")
    (host_python / "python.exe").write_text("exe", encoding="utf-8")
    (host_python / "python3.14t.exe").write_text("exe", encoding="utf-8")
    (host_python / "pythonw.exe").write_text("exe", encoding="utf-8")
    (host_python / "pythonw3.14t.exe").write_text("exe", encoding="utf-8")
    (host_python / "python314t.dll").write_text("dll", encoding="utf-8")
    (host_python / "python3t.dll").write_text("stable ABI", encoding="utf-8")

    monkeypatch.setattr(sdk_bundled_python, "_is_windows", lambda: True)
    monkeypatch.setattr(sdk_verification, "_is_windows", lambda: True)

    sdk._copy_windows_python_runtime_executables(
        sdk_prefix,
        {
            "base_prefix": str(host_python),
            "prefix": str(host_python),
            "base_executable": str(host_python / "python.exe"),
            "executable": str(host_python / "python.exe"),
        },
    )

    assert not (sdk_prefix / "bin" / "python312.dll").exists()
    assert not (sdk_prefix / "python" / "python312.dll").exists()
    assert not (sdk_prefix / "python" / "python3.12.exe").exists()
    assert (sdk_prefix / "bin" / "python314t.dll").is_file()
    assert (sdk_prefix / "bin" / "python3t.dll").is_file()
    assert (sdk_prefix / "python" / "python.exe").is_file()
    assert (sdk_prefix / "python" / "python3.14t.exe").is_file()
    assert (sdk_prefix / "python" / "pythonw.exe").is_file()
    assert (sdk_prefix / "python" / "pythonw3.14t.exe").is_file()
    assert (sdk_prefix / "python" / "python314t.dll").is_file()
    assert (sdk_prefix / "python" / "python3t.dll").is_file()
    assert sdk.verify_no_duplicate_libraries(sdk_prefix) == 0


def test_verify_duplicate_libraries_allows_pyglfw_backend_libraries(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    (sdk_prefix / "bin").mkdir(parents=True)
    glfw_dir = sdk_prefix / "lib" / "python3.10" / "site-packages" / "glfw"
    x11_dir = glfw_dir / "x11"
    wayland_dir = glfw_dir / "wayland"
    x11_dir.mkdir(parents=True)
    wayland_dir.mkdir(parents=True)
    (x11_dir / "libglfw.so").write_text("x11", encoding="utf-8")
    (wayland_dir / "libglfw.so").write_text("wayland", encoding="utf-8")

    monkeypatch.setattr(sdk_verification, "_is_windows", lambda: False)

    assert sdk.verify_no_duplicate_libraries(sdk_prefix) == 0
