import base64
import hashlib
import importlib.metadata
import json
from pathlib import Path

import pytest
from setuptools import Distribution
from setuptools.config.pyprojecttoml import apply_configuration

from termin_build import (
    artifact_manifest,
    sdk,
    sdk_python_layout,
    sdk_runtime_metadata,
    sdk_verification,
)
from termin_build.package_manifest import NativeExtension, PackageEntry
from termin_build.setup_helpers import native_extensions_for_source


def _write_test_distribution(
    site_packages: Path,
    name: str,
    version: str,
    module_name: str,
) -> Path:
    module_path = site_packages / f"{module_name}.py"
    module_path.write_text("VALUE = 1\n", encoding="utf-8")
    digest = base64.urlsafe_b64encode(hashlib.sha256(module_path.read_bytes()).digest())
    encoded = digest.rstrip(b"=").decode("ascii")
    metadata = site_packages / f"{name.replace('-', '_')}-{version}.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        f"Name: {name}\nVersion: {version}\n",
        encoding="utf-8",
    )
    (metadata / "RECORD").write_text(
        f"{module_path.name},sha256={encoded},{module_path.stat().st_size}\n"
        f"{metadata.name}/RECORD,,\n",
        encoding="utf-8",
    )
    return module_path


def _write_empty_artifact_manifest(sdk_prefix: Path) -> None:
    artifacts: list[dict[str, object]] = []
    (sdk_prefix / artifact_manifest.SDK_MANIFEST_NAME).write_text(
        json.dumps(
            {
                "schema": artifact_manifest.SCHEMA_VERSION,
                "manifest_kind": artifact_manifest.SDK_MANIFEST_KIND,
                "native_build_id": artifact_manifest.compute_native_build_id(artifacts),
                "artifacts": artifacts,
            }
        ),
        encoding="utf-8",
    )


def test_build_tools_package_config_excludes_generated_build_tree():
    repo_root = sdk.repo_root_from(Path(__file__))
    distribution = Distribution()

    apply_configuration(distribution, repo_root / "termin-build-tools" / "pyproject.toml")

    assert distribution.packages == ["termin_build"]


def test_python_interpreter_rejects_conflicting_overrides(tmp_path, monkeypatch):
    first = tmp_path / "python-a"
    second = tmp_path / "python-b"
    first.write_text("", encoding="utf-8")
    second.write_text("", encoding="utf-8")
    monkeypatch.setenv("PYTHON_BIN", str(first))
    monkeypatch.setenv("PYTHON_EXECUTABLE", str(second))

    with pytest.raises(RuntimeError, match="different interpreters"):
        sdk_python_layout._python_executable()


def test_sdk_build_propagates_one_absolute_python_to_child_stages(
    tmp_path,
    monkeypatch,
):
    interpreter = tmp_path / "python"
    interpreter.write_text("", encoding="utf-8")
    monkeypatch.setattr(sdk, "_python_executable", lambda: str(interpreter))
    captured = []

    def run(command, *, cwd, env=None):
        captured.append((command, cwd, env))
        return 1

    monkeypatch.setattr(sdk, "_run", run)

    result = sdk.run_sdk_build(
        repo_root=tmp_path,
        build_type="Release",
        stage_args=[],
        build_wheels=False,
        build_csharp=False,
        dry_run=False,
    )

    assert result == 1
    assert len(captured) == 1
    child_env = captured[0][2]
    assert child_env["PYTHON_BIN"] == str(interpreter)
    assert child_env["PYTHON_EXECUTABLE"] == str(interpreter)


def test_windows_dry_run_uses_powershell_stages_and_windows_python_layout(
    tmp_path,
    monkeypatch,
    capsys,
):
    repo_root = tmp_path / "termin"
    repo_root.mkdir()
    sdk_prefix = repo_root / "sdk"

    monkeypatch.setattr(sdk.sys, "platform", "win32")
    monkeypatch.setenv("SDK_PREFIX", str(sdk_prefix))
    monkeypatch.setattr(
        sdk.shutil,
        "which",
        lambda name: "C:/Program Files/PowerShell/7/pwsh.exe"
        if name == "pwsh"
        else None,
    )

    result = sdk.run_sdk_build(
        repo_root=repo_root,
        build_type="Release",
        stage_args=["--no-parallel"],
        build_wheels=False,
        build_csharp=True,
        dry_run=True,
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "pwsh.exe -ExecutionPolicy Bypass -File" in output
    assert "build-sdk-bindings.ps1 --no-parallel" in output
    assert "build-sdk-csharp.ps1 --no-parallel" in output
    assert "sdk/python/Lib/site-packages" in output.replace("\\", "/")


def test_linux_sdk_build_skips_csharp_unless_requested(tmp_path, monkeypatch, capsys):
    interpreter = tmp_path / "python"
    interpreter.write_text("", encoding="utf-8")
    monkeypatch.setattr(sdk, "_python_executable", lambda: str(interpreter))

    result = sdk.run_sdk_build(
        repo_root=tmp_path,
        build_type="Release",
        stage_args=[],
        build_wheels=False,
        build_csharp=False,
        dry_run=True,
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "build-sdk-bindings.sh" in output
    assert "build-sdk-csharp.sh" not in output
    assert "Skipping C# bindings (use --csharp on Linux)." in output


def test_linux_sdk_build_can_request_csharp(tmp_path, monkeypatch, capsys):
    interpreter = tmp_path / "python"
    interpreter.write_text("", encoding="utf-8")
    monkeypatch.setattr(sdk, "_python_executable", lambda: str(interpreter))

    result = sdk.run_sdk_build(
        repo_root=tmp_path,
        build_type="Release",
        stage_args=[],
        build_wheels=False,
        build_csharp=True,
        dry_run=True,
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "build-sdk-csharp.sh" in output


def test_wheelhouse_arg_parser_keeps_stage_args_but_extracts_wheel_options(tmp_path):
    sdk_prefix = tmp_path / "sdk"
    build_dir = tmp_path / "build" / "Release"

    wheel_dir, effective_build_dir, force = sdk._parse_wheelhouse_args(
        sdk_prefix,
        build_dir,
        ["--no-parallel", "--wheel-dir", str(tmp_path / "wheels"), "--force"],
    )

    assert wheel_dir == tmp_path / "wheels"
    assert effective_build_dir == build_dir
    assert force is True


def test_native_extensions_for_source_reads_manifest():
    repo_root = sdk.repo_root_from(Path(__file__))
    extensions = native_extensions_for_source(repo_root / "termin-base")

    assert [extension.name for extension in extensions] == [
        "tcbase._tcbase_native",
        "tcbase._geom_native",
    ]


def test_sdk_runtime_seed_includes_pytest_and_excludes_heavy_optional_packages():
    repo_root = sdk.repo_root_from(Path(__file__))
    runtime_requirement_names = set(sdk._load_runtime_lock(repo_root))

    assert "scipy" not in runtime_requirement_names
    assert "pyopengl" not in runtime_requirement_names
    assert runtime_requirement_names == {
        "colorama",
        "exceptiongroup",
        "glfw",
        "iniconfig",
        "numpy",
        "packaging",
        "pluggy",
        "pygments",
        "pyassimp",
        "pytest",
        "pyyaml",
        "tomli",
        "typing-extensions",
        "watchdog",
    }


def test_repo_installs_umbrella_termin_cmake_package():
    repo_root = sdk.repo_root_from(Path(__file__))
    root_cmake = (repo_root / "CMakeLists.txt").read_text(encoding="utf-8")
    package_config = (repo_root / "cmake" / "terminConfig.cmake.in").read_text(
        encoding="utf-8"
    )

    assert "cmake/terminConfig.cmake.in" in root_cmake
    assert "DESTINATION lib/cmake/termin" in root_cmake
    assert "find_dependency(termin_base CONFIG REQUIRED)" in package_config
    assert "add_library(termin::termin INTERFACE IMPORTED)" in package_config
    assert "INTERFACE_LINK_LIBRARIES tcbase::termin_base" in package_config


def test_openxr_package_declares_all_public_target_dependencies():
    repo_root = sdk.repo_root_from(Path(__file__))
    package_config = (
        repo_root / "termin-openxr/cmake/termin_openxrConfig.cmake.in"
    ).read_text(encoding="utf-8")

    expected_dependencies = {
        "termin_base",
        "termin_scene",
        "termin_mesh",
        "termin_components_mesh",
        "termin_inspect",
        "termin_components_render",
        "termin_graphics",
        "termin_render",
        "termin_render_passes",
        "termin_engine",
        "termin_runtime",
        "termin_collision",
        "termin_input",
    }
    for dependency in expected_dependencies:
        assert f"find_dependency({dependency} CONFIG REQUIRED)" in package_config


def test_write_android_capabilities_records_placeholder_and_full_abis(tmp_path):
    sdk_root = tmp_path / "sdk"
    android_sdk_root = sdk_root / "android"
    vulkan_library = tmp_path / "ndk/libvulkan.so"
    vulkan_library.parent.mkdir(parents=True)
    vulkan_library.write_bytes(b"vulkan")

    placeholder_build = tmp_path / "build-placeholder"
    placeholder_build.mkdir()
    (placeholder_build / "CMakeCache.txt").write_text(
        "TERMIN_OPENXR_HAS_HEADERS:INTERNAL=OFF\n"
        "TERMIN_ENABLE_VULKAN:BOOL=ON\n"
        f"ANDROID_VULKAN_LIB:FILEPATH={vulkan_library}\n",
        encoding="utf-8",
    )
    assert sdk.write_android_capabilities(
        sdk_root=sdk_root,
        android_sdk_root=android_sdk_root,
        abi="x86_64",
        build_dir=placeholder_build,
    ) == 0

    full_prefix = android_sdk_root / "arm64-v8a"
    loader = full_prefix / "lib/libopenxr_loader.so"
    loader.parent.mkdir(parents=True)
    loader.write_bytes(b"openxr")
    full_build = tmp_path / "build-full"
    full_build.mkdir()
    (full_build / "CMakeCache.txt").write_text(
        "TERMIN_OPENXR_HAS_HEADERS:INTERNAL=ON\n"
        "TERMIN_ENABLE_VULKAN:BOOL=ON\n"
        f"ANDROID_VULKAN_LIB:FILEPATH={vulkan_library}\n",
        encoding="utf-8",
    )
    assert sdk.write_android_capabilities(
        sdk_root=sdk_root,
        android_sdk_root=android_sdk_root,
        abi="arm64-v8a",
        build_dir=full_build,
    ) == 0

    placeholder = json.loads(
        (android_sdk_root / "x86_64/share/termin/android-capabilities.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (sdk_root / "termin-sdk-capabilities.json").read_text(encoding="utf-8")
    )
    assert placeholder["openxr_headers"] is False
    assert placeholder["openxr_loader"] is False
    assert placeholder["vulkan"] is True
    assert manifest["platforms"]["android"] == {
        "abis": ["arm64-v8a", "x86_64"],
        "python_runtime": False,
        "vulkan": True,
    }
    assert manifest["platforms"]["quest_openxr"] == {
        "abis": ["arm64-v8a"],
        "openxr_headers": True,
        "openxr_loader": True,
        "vulkan": True,
    }


def test_install_target_uses_single_pip_invocation(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    target_dir = tmp_path / "target"
    (sdk_prefix / "lib").mkdir(parents=True)
    for package_path in ("pkg-a", "pkg-b"):
        (repo_root / package_path).mkdir(parents=True)

    packages = [
        PackageEntry("pkg-a", "pkg-a", (), ()),
        PackageEntry("pkg-b", "pkg-b", (), ()),
    ]
    commands = []

    monkeypatch.setattr(sdk, "load_manifest", lambda _repo_root: packages)
    monkeypatch.setattr(sdk, "_python_bin", lambda: "python")
    monkeypatch.setattr(
        sdk,
        "_run",
        lambda command, **_kwargs: commands.append(command) or 0,
    )
    stale_pkg_a = target_dir / "pkg_a-0.1.0+old.dist-info"
    stale_pkg_a.mkdir(parents=True)
    (stale_pkg_a / "METADATA").write_text("Name: pkg-a\n", encoding="utf-8")
    stale_pkg_a_module = target_dir / "pkg_a" / "removed_module.py"
    stale_pkg_a_module.parent.mkdir()
    stale_pkg_a_module.write_text("STALE = True\n", encoding="utf-8")
    (stale_pkg_a / "RECORD").write_text(
        "pkg_a/removed_module.py,,\n"
        "pkg_a-0.1.0+old.dist-info/METADATA,,\n",
        encoding="utf-8",
    )
    stale_pkg_b = target_dir / "pkg_b.egg-info"
    stale_pkg_b.mkdir()
    (stale_pkg_b / "PKG-INFO").write_text("Name: pkg-b\n", encoding="utf-8")
    unrelated = target_dir / "unrelated-1.0.0.dist-info"
    unrelated.mkdir()
    (unrelated / "METADATA").write_text("Name: unrelated\n", encoding="utf-8")

    result = sdk.install_pip_packages(
        repo_root=repo_root,
        sdk_prefix=sdk_prefix,
        build_dir=repo_root / "build" / "Release",
        target_dir=target_dir,
        editable=False,
        force=True,
    )

    assert result == 0
    assert len(commands) == 1
    command = commands[0]
    assert command[:6] == [
        "python",
        "-m",
        "pip",
        "install",
        "--no-build-isolation",
        "--no-deps",
    ]
    assert "--target" in command
    assert command.count("--no-deps") == 1
    assert str(repo_root / "pkg-a") in command
    assert str(repo_root / "pkg-b") in command
    assert not stale_pkg_a.exists()
    assert not stale_pkg_a_module.exists()
    assert not stale_pkg_b.exists()
    assert unrelated.is_dir()


def test_target_metadata_cleanup_does_not_follow_record_paths_outside_target(
    tmp_path,
):
    target_dir = tmp_path / "site-packages"
    metadata = target_dir / "pkg_a-0.1.0.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "METADATA").write_text("Name: pkg-a\n", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("KEEP = True\n", encoding="utf-8")
    (metadata / "RECORD").write_text(
        "../../outside.py,,\n",
        encoding="utf-8",
    )

    sdk_runtime_metadata._clear_target_distribution_metadata(target_dir, {"pkg-a"})

    assert outside.is_file()
    assert not metadata.exists()


def test_verify_sdk_python_launcher_rejects_missing_launcher(tmp_path, capsys):
    sdk_prefix = tmp_path / "sdk"

    assert sdk.verify_sdk_python_launcher(sdk_prefix) == 1
    assert "SDK Python launcher is missing" in capsys.readouterr().err


@pytest.mark.parametrize("is_windows", [False, True])
def test_verify_sdk_python_launcher_checks_platform_layout_isolation_and_imports(
    tmp_path,
    monkeypatch,
    is_windows,
):
    sdk_prefix = tmp_path / "sdk"
    python_home = sdk_prefix / "python" if is_windows else sdk_prefix
    launcher_name = "termin_python.exe" if is_windows else "termin_python"
    launcher = sdk_prefix / "bin" / launcher_name
    launcher.parent.mkdir(parents=True)
    launcher.write_text("launcher", encoding="utf-8")
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        if "--termin-info" in command:
            return sdk.subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "sdk_root": str(sdk_prefix.resolve()),
                        "python_home": str(python_home.resolve()),
                        "isolated": True,
                        "use_environment": False,
                        "user_site": False,
                    }
                ),
                stderr="",
            )
        return sdk.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(sdk_verification, "_is_windows", lambda: is_windows)
    monkeypatch.setattr(sdk.subprocess, "run", fake_run)

    assert sdk.verify_sdk_python_launcher(sdk_prefix) == 0
    assert len(commands) == 2
    assert "termin.engine" in commands[1][0][-1]
    for _command, kwargs in commands:
        assert kwargs["env"]["PYTHONHOME"].endswith("__invalid_python_home__")
        assert kwargs["env"]["PYTHONPATH"].endswith("__invalid_python_path__")


def test_force_package_cache_cleanup_removes_plain_build_lib_and_nested_egg_info(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    package_root = repo_root / "example"
    stale_build_lib = package_root / "build" / "lib" / "example"
    stale_build_lib.mkdir(parents=True)
    (stale_build_lib / "removed.py").write_text("STALE = True\n", encoding="utf-8")
    nested_egg_info = package_root / "python" / "example.egg-info"
    nested_egg_info.mkdir(parents=True)
    (nested_egg_info / "SOURCES.txt").write_text("removed.py\n", encoding="utf-8")
    monkeypatch.setattr(
        sdk,
        "load_manifest",
        lambda _repo_root: [PackageEntry("example", "example", (), ())],
    )

    sdk._clear_python_package_build_caches(repo_root)

    assert not (package_root / "build" / "lib").exists()
    assert not nested_egg_info.exists()


def test_external_runtime_wheels_are_built_from_exact_lock(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    lock_path = repo_root / sdk.RUNTIME_LOCK_RELATIVE
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("numpy==2.2.6\nwatchdog==6.0.0\n", encoding="utf-8")
    wheel_dir = repo_root / "build" / "python-runtime" / "external-wheels"
    commands = []

    monkeypatch.setattr(sdk, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk,
        "_run",
        lambda command, **_kwargs: commands.append(command) or 0,
    )

    result = sdk._prepare_external_runtime_wheels(repo_root, wheel_dir, Path("python"))

    assert result == 0
    assert commands == [
        [
            "python",
            "-m",
            "pip",
            "wheel",
            "--no-build-isolation",
            "--no-deps",
            "--wheel-dir",
            str(wheel_dir),
            "-r",
            str(lock_path),
        ]
    ]


def test_sdk_python_build_environment_uses_pinned_tools(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    requirements = repo_root / sdk.SDK_BUILD_REQUIREMENTS_RELATIVE
    requirements.parent.mkdir(parents=True)
    requirements.write_text("pip==26.1.2\nsetuptools==83.0.0\n", encoding="utf-8")
    environment_root = repo_root / "build" / "python-runtime" / "build-env"
    build_python = environment_root / "bin" / "python"
    build_python.parent.mkdir(parents=True)
    build_python.touch()
    commands = []
    monkeypatch.setattr(sdk, "_is_windows", lambda: False)
    monkeypatch.setattr(
        sdk,
        "_run",
        lambda command, **_kwargs: commands.append(command) or 0,
    )

    result = sdk._ensure_sdk_python_build_environment(repo_root)

    assert result == build_python
    assert commands == [
        [
            str(build_python),
            "-I",
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--no-deps",
            "-r",
            str(requirements),
        ]
    ]
    assert (environment_root / "python-sdk-build-requirements.txt").read_bytes() == (
        requirements.read_bytes()
    )


def test_bundled_python_runtime_copies_shared_libpython_and_drops_config_artifacts(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    stdlib = tmp_path / "host" / "lib" / "python3.10"
    libdir = tmp_path / "host" / "lib"
    config_dir = stdlib / "config-3.10-x86_64-linux-gnu"
    config_dir.mkdir(parents=True)
    (config_dir / "libpython3.10.a").write_bytes(b"static")
    (stdlib / "ensurepip").mkdir()
    (stdlib / "ctypes").mkdir()
    (stdlib / "ctypes" / "__init__.py").write_text("", encoding="utf-8")
    (libdir / "libpython3.10.so.1.0").write_bytes(b"shared")

    monkeypatch.setattr(sdk, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk,
        "_python_version_and_paths",
        lambda _py_exec: {
            "version": "3.10",
            "stdlib": str(stdlib),
            "libdir": str(libdir),
            "sitepackages": [],
        },
    )

    bundled_py_dir = sdk.ensure_bundled_python_runtime(sdk_prefix)

    assert bundled_py_dir == sdk_prefix / "lib" / "python3.10"
    assert (sdk_prefix / "lib" / "libpython3.10.so.1.0").read_bytes() == b"shared"
    assert not (bundled_py_dir / "config-3.10-x86_64-linux-gnu").exists()
    assert (bundled_py_dir / "ctypes" / "__init__.py").is_file()


def test_sdk_python_install_repairs_existing_runtime_shared_libpython(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    build_dir = repo_root / "build" / "Release"
    bundled_py_dir = sdk_prefix / "lib" / "python3.10"
    site_packages = bundled_py_dir / "site-packages"
    host_libdir = tmp_path / "host" / "lib"
    config_dir = bundled_py_dir / "config-3.10-x86_64-linux-gnu"
    (bundled_py_dir / "ensurepip").mkdir(parents=True)
    site_packages.mkdir()
    config_dir.mkdir()
    (config_dir / "libpython3.10.a").write_bytes(b"static")
    host_libdir.mkdir(parents=True)
    (host_libdir / "libpython3.10.so.1.0").write_bytes(b"shared")
    (build_dir / "bin").mkdir(parents=True)

    monkeypatch.setattr(sdk, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_runtime_metadata, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk,
        "_python_version_and_paths",
        lambda _py_exec: {
            "version": "3.10",
            "stdlib": str(tmp_path / "unused"),
            "libdir": str(host_libdir),
            "sitepackages": [],
        },
    )
    monkeypatch.setattr(sdk, "ensure_bundled_python_cli", lambda _sdk_prefix: None)
    monkeypatch.setattr(
        sdk,
        "_ensure_sdk_python_build_environment",
        lambda _root: Path("build-python"),
    )
    monkeypatch.setattr(sdk, "_prepare_external_runtime_wheels", lambda *_args: 0)
    monkeypatch.setattr(sdk, "_build_local_package_wheels", lambda **_kwargs: 0)
    monkeypatch.setattr(sdk, "_install_prepared_runtime_wheels", lambda **_kwargs: 0)
    monkeypatch.setattr(sdk, "write_python_runtime_manifest", lambda *_args: Path("manifest"))

    result = sdk.install_python_packages(
        repo_root=repo_root,
        sdk_prefix=sdk_prefix,
        build_dir=build_dir,
    )

    assert result == 0
    assert (sdk_prefix / "lib" / "libpython3.10.so.1.0").read_bytes() == b"shared"
    assert not config_dir.exists()


def test_prepare_build_python_runtime_sanitizes_sdk_before_cmake(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    bundled_py_dir = sdk_prefix / "lib" / "python3.10"
    config_dir = bundled_py_dir / "config-3.10-x86_64-linux-gnu"
    host_libdir = tmp_path / "host" / "lib"
    config_dir.mkdir(parents=True)
    (config_dir / "libpython3.10.a").write_bytes(b"static")
    host_libdir.mkdir(parents=True)
    (host_libdir / "libpython3.10.so").write_bytes(b"shared")

    monkeypatch.setattr(sdk, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk,
        "_python_version_and_paths",
        lambda _py_exec: {
            "version": "3.10",
            "stdlib": str(tmp_path / "unused"),
            "libdir": str(host_libdir),
            "sitepackages": [],
        },
    )

    result = sdk.prepare_build_python_runtime(sdk_prefix)

    assert result == 0
    assert not config_dir.exists()
    assert (sdk_prefix / "lib" / "libpython3.10.so").read_bytes() == b"shared"


def test_prepare_build_python_runtime_creates_runtime_for_clean_sdk(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    stdlib = tmp_path / "host" / "lib" / "python3.10"
    host_libdir = tmp_path / "host" / "lib"
    (stdlib / "ensurepip").mkdir(parents=True)
    (stdlib / "os.py").write_text("", encoding="utf-8")
    (host_libdir / "libpython3.10.so").write_bytes(b"shared")

    monkeypatch.setattr(sdk, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk,
        "_python_version_and_paths",
        lambda _py_exec: {
            "version": "3.10",
            "stdlib": str(stdlib),
            "libdir": str(host_libdir),
            "sitepackages": [],
        },
    )

    result = sdk.prepare_build_python_runtime(sdk_prefix)

    assert result == 0
    assert (sdk_prefix / "lib" / "python3.10" / "os.py").is_file()
    assert (sdk_prefix / "lib" / "python3.10" / "site-packages").is_dir()
    assert (sdk_prefix / "lib" / "libpython3.10.so").read_bytes() == b"shared"


def test_sdk_python_layout_rejects_multiple_runtime_abis(tmp_path, monkeypatch):
    sdk_prefix = tmp_path / "sdk"
    (sdk_prefix / "lib" / "python3.10" / "site-packages").mkdir(parents=True)
    (sdk_prefix / "lib" / "python3.12" / "site-packages").mkdir(parents=True)

    monkeypatch.setattr(sdk_python_layout, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_python_layout, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_layout,
        "_python_version_and_paths",
        lambda _py_exec: {"version": "3.10"},
    )

    with pytest.raises(RuntimeError, match="multiple bundled Python runtimes"):
        sdk.resolve_sdk_python_layout(sdk_prefix)


def test_sdk_python_layout_rejects_active_python_abi_mismatch(tmp_path, monkeypatch):
    sdk_prefix = tmp_path / "sdk"
    (sdk_prefix / "lib" / "python3.12" / "site-packages").mkdir(parents=True)

    monkeypatch.setattr(sdk_python_layout, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_python_layout, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_layout,
        "_python_version_and_paths",
        lambda _py_exec: {"version": "3.10"},
    )

    with pytest.raises(RuntimeError, match="SDK Python ABI mismatch"):
        sdk.resolve_sdk_python_layout(sdk_prefix)


def test_sdk_python_layout_can_require_native_bindings(tmp_path, monkeypatch):
    sdk_prefix = tmp_path / "sdk"
    tcbase_dir = sdk_prefix / "lib" / "python3.10" / "site-packages" / "tcbase"
    tcbase_dir.mkdir(parents=True)

    monkeypatch.setattr(sdk_python_layout, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_python_layout, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_layout,
        "_python_version_and_paths",
        lambda _py_exec: {"version": "3.10"},
    )

    with pytest.raises(RuntimeError, match="native bindings were not found"):
        sdk.resolve_sdk_python_layout(sdk_prefix, require_native_bindings=True)

    (tcbase_dir / "_tcbase_native.cpython-310-x86_64-linux-gnu.so").touch()
    assert sdk.resolve_sdk_python_layout(
        sdk_prefix,
        require_native_bindings=True,
    ) == tcbase_dir.parent


def test_publish_cmake_python_install_normalizes_staged_bindings(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    install_dir = tmp_path / "install"
    site_packages = sdk_prefix / "lib" / "python3.10" / "site-packages"
    legacy_tcbase = install_dir / "lib" / "python" / "tcbase"
    staged_package = (
        install_dir
        / "lib"
        / "python3.10"
        / "site-packages"
        / "termin"
        / "editor"
    )
    site_packages.mkdir(parents=True)
    legacy_tcbase.mkdir(parents=True)
    staged_package.mkdir(parents=True)
    native_name = "_tcbase_native.cpython-310-x86_64-linux-gnu.so"
    (legacy_tcbase / native_name).write_bytes(b"native")
    (legacy_tcbase / "__init__.py").write_text("", encoding="utf-8")
    cache_dir = legacy_tcbase / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "__init__.cpython-310.pyc").write_bytes(b"bytecode")
    (staged_package / "runtime.py").write_text("VALUE = 1\n", encoding="utf-8")

    monkeypatch.setattr(sdk_python_layout, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_python_layout, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_layout,
        "_python_version_and_paths",
        lambda _py_exec: {"version": "3.10"},
    )

    result = sdk.publish_cmake_python_install(install_dir, sdk_prefix)

    assert result == site_packages
    assert (site_packages / "tcbase" / native_name).read_bytes() == b"native"
    assert (site_packages / "termin" / "editor" / "runtime.py").read_text() == (
        "VALUE = 1\n"
    )
    assert not (sdk_prefix / "lib" / "python").exists()
    assert not list(site_packages.rglob("__pycache__"))
    assert not list(site_packages.rglob("*.pyc"))


def test_publish_cmake_python_install_removes_windows_legacy_tree(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    site_packages = sdk_prefix / "python" / "Lib" / "site-packages"
    tcbase_dir = site_packages / "tcbase"
    legacy_package = sdk_prefix / "lib" / "python" / "termin" / "sample"
    tcbase_dir.mkdir(parents=True)
    legacy_package.mkdir(parents=True)
    (tcbase_dir / "_tcbase_native.cp310-win_amd64.pyd").write_bytes(b"native")
    (legacy_package / "_sample_native.cp310-win_amd64.pyd").write_bytes(b"sample")

    monkeypatch.setattr(sdk_python_layout, "_is_windows", lambda: True)
    monkeypatch.setattr(sdk_python_layout, "_python_executable", lambda: "python.exe")
    monkeypatch.setattr(
        sdk_python_layout,
        "_python_version_and_paths",
        lambda _py_exec: {"version": "3.10"},
    )

    result = sdk.publish_cmake_python_install(sdk_prefix, sdk_prefix)

    assert result == site_packages
    assert (
        site_packages / "termin" / "sample" / "_sample_native.cp310-win_amd64.pyd"
    ).read_bytes() == b"sample"
    assert not (sdk_prefix / "lib" / "python").exists()


def test_target_metadata_cleanup_keeps_entry_point_discovery_deterministic(tmp_path):
    target_dir = tmp_path / "site-packages"
    target_dir.mkdir()
    old_metadata = target_dir / "termin_voxels-0.1.0+old.dist-info"
    old_metadata.mkdir()
    (old_metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\n"
        "Name: termin-voxels\n"
        "Version: 0.1.0+old\n",
        encoding="utf-8",
    )
    package = PackageEntry("termin-voxels", "termin-voxels", (), ())

    sdk._clear_target_python_package_metadata(target_dir, [package])

    fresh_metadata = target_dir / "termin_voxels-0.1.0+fresh.dist-info"
    fresh_metadata.mkdir()
    (fresh_metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\n"
        "Name: termin-voxels\n"
        "Version: 0.1.0+fresh\n",
        encoding="utf-8",
    )
    (fresh_metadata / "entry_points.txt").write_text(
        "[termin.asset_import_plugins]\n"
        "voxel_grid = termin.default_assets.voxels.asset_plugin:create_import_plugin\n",
        encoding="utf-8",
    )

    distributions = [
        distribution
        for distribution in importlib.metadata.distributions(path=[str(target_dir)])
        if distribution.metadata["Name"] == "termin-voxels"
    ]
    entry_points = [
        entry_point
        for distribution in distributions
        for entry_point in distribution.entry_points
        if entry_point.group == "termin.asset_import_plugins"
    ]

    assert len(distributions) == 1
    assert [entry_point.name for entry_point in entry_points] == ["voxel_grid"]


def test_editable_install_is_sequential_and_no_deps(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    (sdk_prefix / "lib").mkdir(parents=True)
    for package_path in ("pkg-a", "pkg-b"):
        (repo_root / package_path).mkdir(parents=True)

    packages = [
        PackageEntry("pkg-a", "pkg-a", (), ()),
        PackageEntry("pkg-b", "pkg-b", (), ()),
    ]
    commands = []

    monkeypatch.setattr(sdk, "load_manifest", lambda _repo_root: packages)
    monkeypatch.setattr(sdk, "_python_bin", lambda: "python")
    monkeypatch.setattr(
        sdk,
        "_run",
        lambda command, **_kwargs: commands.append(command) or 0,
    )

    result = sdk.install_pip_packages(
        repo_root=repo_root,
        sdk_prefix=sdk_prefix,
        build_dir=repo_root / "build" / "Release",
        target_dir=None,
        editable=True,
        force=False,
    )

    assert result == 0
    assert len(commands) == 2
    for command in commands:
        assert command[:5] == [
            "python",
            "-m",
            "pip",
            "install",
            "--no-build-isolation",
        ]
        assert "--no-deps" in command
        assert "-e" in command


def test_editable_install_removes_legacy_source_native_artifacts(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    legacy_dir = repo_root / "termin-app" / "termin"
    legacy_dir.mkdir(parents=True)
    (sdk_prefix / "lib").mkdir(parents=True)
    stale_artifact = legacy_dir / "_native.cp312-win_amd64.pyd"
    stale_artifact.write_text("old binding", encoding="utf-8")
    keep_artifact = legacy_dir / "_editor_native.cp312-win_amd64.pyd"
    keep_artifact.write_text("current binding", encoding="utf-8")

    packages = [PackageEntry("termin-app", "termin-app", (), ())]
    commands = []

    monkeypatch.setattr(sdk, "load_manifest", lambda _repo_root: packages)
    monkeypatch.setattr(sdk, "_python_bin", lambda: "python")
    monkeypatch.setattr(
        sdk,
        "_run",
        lambda command, **_kwargs: commands.append(command) or 0,
    )

    result = sdk.install_pip_packages(
        repo_root=repo_root,
        sdk_prefix=sdk_prefix,
        build_dir=repo_root / "build" / "Release",
        target_dir=None,
        editable=True,
        force=False,
    )

    assert result == 0
    assert not stale_artifact.exists()
    assert keep_artifact.is_file()
    assert len(commands) == 1


def test_editable_install_failure_reports_windows_native_lock_context(
    tmp_path,
    monkeypatch,
    capsys,
):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    package_root = repo_root / "termin-input"
    native_dir = package_root / "python" / "termin" / "input"
    native_dir.mkdir(parents=True)
    (sdk_prefix / "lib").mkdir(parents=True)
    native_artifact = native_dir / "_input_native.cp310-win_amd64.pyd"
    native_artifact.write_text("native", encoding="utf-8")

    packages = [PackageEntry("termin-input", "termin-input", (), ())]

    monkeypatch.setattr(sdk, "load_manifest", lambda _repo_root: packages)
    monkeypatch.setattr(sdk, "_python_bin", lambda: "python")
    monkeypatch.setattr(sdk, "_is_windows", lambda: True)
    monkeypatch.setattr(
        sdk,
        "_run",
        lambda _command, **_kwargs: 1,
    )
    monkeypatch.setattr(
        sdk,
        "_windows_module_users",
        lambda module_name: [f"python.exe 123 Console 1 100 K {module_name}"],
    )
    monkeypatch.setattr(
        sdk,
        "_windows_python_processes",
        lambda: ["python.exe 123 Console 1 100 K"],
    )

    result = sdk.install_pip_packages(
        repo_root=repo_root,
        sdk_prefix=sdk_prefix,
        build_dir=repo_root / "build" / "Release",
        target_dir=None,
        editable=True,
        force=False,
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "pip install failed for termin-input (1/1)" in captured.err
    assert "Python package sync stopped" in captured.err
    assert str(native_artifact) in captured.err
    assert "python.exe 123" in captured.err
    assert "install-pip-packages.ps1 --editable --force" in captured.err


@pytest.mark.parametrize(
    ("is_windows", "bundled_python_parts"),
    [
        (False, ("lib", "python3.10")),
        (True, ("python", "Lib")),
    ],
)
def test_sdk_python_install_builds_wheels_then_installs_offline_and_writes_manifest(
    tmp_path,
    monkeypatch,
    is_windows,
    bundled_python_parts,
):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    build_dir = repo_root / "build" / "Release"
    bundled_py_dir = sdk_prefix.joinpath(*bundled_python_parts)
    site_packages = bundled_py_dir / "site-packages"
    (bundled_py_dir / "ensurepip").mkdir(parents=True)
    (sdk_prefix / "lib").mkdir(exist_ok=True)
    (build_dir / "bin").mkdir(parents=True)
    if not is_windows:
        (sdk_prefix / "lib" / "libpython3.10.so").write_bytes(b"shared")

    calls = []

    monkeypatch.setattr(sdk, "_is_windows", lambda: is_windows)
    monkeypatch.setattr(sdk_python_layout, "_is_windows", lambda: is_windows)
    monkeypatch.setattr(sdk, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk,
        "_python_version_and_paths",
        lambda _py_exec: {
            "version": "3.10",
            "stdlib": str(tmp_path / "unused"),
            "libdir": str(tmp_path / "unused"),
            "sitepackages": [],
        },
    )
    monkeypatch.setattr(sdk, "ensure_bundled_python_cli", lambda _sdk_prefix: None)
    monkeypatch.setattr(
        sdk,
        "_ensure_sdk_python_build_environment",
        lambda _root: Path("build-python"),
    )
    monkeypatch.setattr(sdk, "_runtime_wheel_dirs", lambda _root: (Path("external"), Path("local")))
    monkeypatch.setattr(
        sdk,
        "_prepare_external_runtime_wheels",
        lambda root, wheels, python: calls.append(
            ("external", root, wheels, python)
        )
        or 0,
    )
    monkeypatch.setattr(
        sdk,
        "_build_local_package_wheels",
        lambda **kwargs: calls.append(("build", kwargs)) or 0,
    )
    monkeypatch.setattr(
        sdk,
        "_install_prepared_runtime_wheels",
        lambda **kwargs: calls.append(("install", kwargs)) or 0,
    )
    monkeypatch.setattr(
        sdk,
        "write_python_runtime_manifest",
        lambda *args: calls.append(("manifest", args)) or Path("manifest"),
    )

    result = sdk.install_python_packages(
        repo_root=repo_root,
        sdk_prefix=sdk_prefix,
        build_dir=build_dir,
    )

    assert result == 0
    assert [call[0] for call in calls] == ["external", "build", "install", "manifest"]
    assert calls[2][1]["site_packages"] == site_packages
    assert calls[2][1]["external_wheels"] == Path("external")
    assert calls[2][1]["local_wheels"] == Path("local")
    assert calls[3][1] == (repo_root, sdk_prefix, site_packages)


def test_install_packages_rejects_unknown_options(capsys):
    result = sdk.main(
        [
            "--repo-root",
            str(sdk.repo_root_from(Path(__file__))),
            "install-packages",
            "--unknown-option",
        ]
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "unknown install-packages option" in captured.err


def test_runtime_manifest_records_declared_distributions_and_verifies_hashes(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    site_packages = sdk_prefix / "lib" / "python3.10" / "site-packages"
    site_packages.mkdir(parents=True)
    _write_empty_artifact_manifest(sdk_prefix)
    lock_path = repo_root / sdk.RUNTIME_LOCK_RELATIVE
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("numpy==2.2.6\n", encoding="utf-8")
    _write_test_distribution(site_packages, "numpy", "2.2.6", "numpy_stub")
    _write_test_distribution(
        site_packages,
        "termin-example",
        "0.1.0",
        "termin_example",
    )
    monkeypatch.setattr(
        sdk_runtime_metadata,
        "load_manifest",
        lambda _root: [PackageEntry("example", "termin-example", (), ())],
    )
    monkeypatch.setattr(
        sdk_runtime_metadata,
        "_python_version_and_paths",
        lambda _python: {"version": "3.10"},
    )
    monkeypatch.setattr(sdk_runtime_metadata, "_python_executable", lambda: "python")

    output = sdk.write_python_runtime_manifest(repo_root, sdk_prefix, site_packages)

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["python_abi"] == "3.10"
    assert [entry["kind"] for entry in data["distributions"]] == [
        "runtime",
        "termin",
    ]
    assert sdk.verify_python_runtime_manifest(sdk_prefix) == 0


def test_runtime_manifest_rejects_undeclared_and_modified_distributions(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    site_packages = sdk_prefix / "lib" / "python3.10" / "site-packages"
    site_packages.mkdir(parents=True)
    _write_empty_artifact_manifest(sdk_prefix)
    lock_path = repo_root / sdk.RUNTIME_LOCK_RELATIVE
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("numpy==2.2.6\n", encoding="utf-8")
    payload = _write_test_distribution(site_packages, "numpy", "2.2.6", "numpy_stub")
    monkeypatch.setattr(sdk_runtime_metadata, "load_manifest", lambda _root: [])
    monkeypatch.setattr(
        sdk_runtime_metadata,
        "_python_version_and_paths",
        lambda _python: {"version": "3.10"},
    )
    monkeypatch.setattr(sdk_runtime_metadata, "_python_executable", lambda: "python")
    sdk.write_python_runtime_manifest(repo_root, sdk_prefix, site_packages)

    payload.write_text("VALUE = 2\n", encoding="utf-8")
    _write_test_distribution(site_packages, "unexpected", "1.0", "unexpected")

    assert sdk.verify_python_runtime_manifest(sdk_prefix) == 1


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

    build_artifact = build_bin / "_sample_native.cpython-310-x86_64-linux-gnu.so"
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
    assert data["schema"] == 2
    assert data["manifest_kind"] == "termin-sdk-artifacts"
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
    build_data = json.loads(
        (build_dir / "termin-build-artifacts.json").read_text()
    )
    assert build_data["manifest_kind"] == "termin-build-artifacts"
    assert build_data["artifacts"][0]["path"] == str(build_artifact.resolve())


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

    monkeypatch.setattr(sdk, "_is_windows", lambda: True)

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

    monkeypatch.setattr(sdk, "_is_windows", lambda: True)

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

    monkeypatch.setattr(sdk, "_is_windows", lambda: True)

    assert sdk.verify_no_duplicate_libraries(sdk_prefix) == 0


def test_windows_python_runtime_copies_cli_and_allows_python_home_dll(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    host_python = tmp_path / "host-python"
    host_python.mkdir()
    (host_python / "python.exe").write_text("exe", encoding="utf-8")
    (host_python / "pythonw.exe").write_text("exe", encoding="utf-8")
    (host_python / "python312.dll").write_text("dll", encoding="utf-8")

    monkeypatch.setattr(sdk, "_is_windows", lambda: True)

    sdk._copy_windows_python_runtime_executables(
        sdk_prefix,
        {
            "base_prefix": str(host_python),
            "prefix": str(host_python),
            "base_executable": str(host_python / "python.exe"),
            "executable": str(host_python / "python.exe"),
        },
    )

    assert (sdk_prefix / "bin" / "python312.dll").is_file()
    assert (sdk_prefix / "python" / "python.exe").is_file()
    assert (sdk_prefix / "python" / "pythonw.exe").is_file()
    assert (sdk_prefix / "python" / "python312.dll").is_file()
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

    monkeypatch.setattr(sdk, "_is_windows", lambda: False)

    assert sdk.verify_no_duplicate_libraries(sdk_prefix) == 0
