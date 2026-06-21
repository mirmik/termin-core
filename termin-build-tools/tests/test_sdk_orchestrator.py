import importlib.metadata
import json
from pathlib import Path

from termin_build import sdk
from termin_build.package_manifest import NativeExtension, PackageEntry
from termin_build.setup_helpers import native_extensions_for_source


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
        dry_run=True,
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "pwsh.exe -ExecutionPolicy Bypass -File" in output
    assert "build-sdk-bindings.ps1 --no-parallel" in output
    assert "build-sdk-csharp.ps1 --no-parallel" in output
    assert "sdk/python/Lib/site-packages" in output.replace("\\", "/")


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
    assert not stale_pkg_b.exists()
    assert unrelated.is_dir()


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
        "voxel_grid = termin.voxels.asset_plugin:create_import_plugin\n",
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
    install_dir = tmp_path / "install"
    build_bin = build_dir / "bin"
    install_pkg = install_dir / "lib" / "python" / "termin" / "sample"
    build_bin.mkdir(parents=True)
    install_pkg.mkdir(parents=True)

    build_artifact = build_bin / "_sample_native.cpython-310-x86_64-linux-gnu.so"
    install_artifact = install_pkg / build_artifact.name
    build_artifact.write_text("native", encoding="utf-8")
    install_artifact.write_text("native", encoding="utf-8")

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
    artifact = data["artifacts"][0]
    assert artifact["build_path"] == str(build_artifact.resolve())
    assert artifact["install_path"] == str(install_artifact.resolve())
    assert artifact["runtime_dependencies"] == ["libtermin_sample.so"]
    assert artifact["features"] == ["sample"]


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
    assert artifact["build_path"] == str(build_artifact.resolve())
    assert artifact["install_path"] == str(install_artifact.resolve())
    assert artifact["runtime_dependencies"] == []


def test_verify_duplicate_libraries_reports_windows_duplicates(
    tmp_path,
    monkeypatch,
    capsys,
):
    sdk_prefix = tmp_path / "sdk"
    (sdk_prefix / "bin").mkdir(parents=True)
    (sdk_prefix / "python" / "Lib" / "site-packages").mkdir(parents=True)
    (sdk_prefix / "bin" / "termin_core.dll").write_text("dll", encoding="utf-8")
    (
        sdk_prefix
        / "python"
        / "Lib"
        / "site-packages"
        / "termin_core.dll"
    ).write_text("dll", encoding="utf-8")

    monkeypatch.setattr(sdk, "_is_windows", lambda: True)

    result = sdk.verify_no_duplicate_libraries(sdk_prefix)

    captured = capsys.readouterr()
    assert result == 1
    assert "DUPLICATE: termin_core.dll" in captured.out


def test_verify_duplicate_libraries_ignores_scoped_sdk_duplicates(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    (sdk_prefix / "bin").mkdir(parents=True)
    (sdk_prefix / "android" / "arm64-v8a").mkdir(parents=True)
    (sdk_prefix / "csharp" / "runtimes" / "win-x64" / "native").mkdir(parents=True)
    (sdk_prefix / "bin" / "termin_core.dll").write_text("dll", encoding="utf-8")
    (sdk_prefix / "android" / "arm64-v8a" / "termin_core.dll").write_text(
        "dll",
        encoding="utf-8",
    )
    (
        sdk_prefix
        / "csharp"
        / "runtimes"
        / "win-x64"
        / "native"
        / "termin_core.dll"
    ).write_text("dll", encoding="utf-8")

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


def test_verify_duplicate_libraries_allows_pysdl2_core_sdl_duplicate(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    (sdk_prefix / "bin").mkdir(parents=True)
    sdl2dll_dir = sdk_prefix / "python" / "Lib" / "site-packages" / "sdl2dll" / "dll"
    sdl2dll_dir.mkdir(parents=True)
    (sdk_prefix / "bin" / "SDL2.dll").write_text("sdk-sdl", encoding="utf-8")
    (sdl2dll_dir / "SDL2.dll").write_text("pysdl2-sdl", encoding="utf-8")

    monkeypatch.setattr(sdk, "_is_windows", lambda: True)

    assert sdk.verify_no_duplicate_libraries(sdk_prefix) == 0
