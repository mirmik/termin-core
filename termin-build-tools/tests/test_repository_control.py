from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest

from termin_build import process_smoke, repository_control


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _repository(tmp_path: Path) -> Path:
    package = tmp_path / "alpha"
    package.mkdir()
    (package / "pyproject.toml").write_text("[project]\nname='alpha'\n", encoding="utf-8")
    tests = package / "tests"
    tests.mkdir()

    _write_json(
        tmp_path / "build-system" / "packages.json",
        {
            "schema": 1,
            "packages": [{"path": "alpha", "distribution": "alpha-dist"}],
        },
    )
    _write_json(
        tmp_path / "build-system" / "modules.json",
        {
            "schema": 1,
            "python_package_manifest": "build-system/packages.json",
            "modules": [],
        },
    )
    _write_json(
        tmp_path / "build-system" / "test-suites.json",
        {
            "schema": 1,
            "python_test_inventory": {
                "patterns": ["test_*.py", "*_test.py"],
                "exclude_roots": ["build", "termin-app/install"],
                "exclude_directory_names": ["__pycache__"],
            },
            "native_test_inventory": {
                "patterns": ["test_*", "tests_*", "*_test.*"],
                "extensions": [".c", ".cc", ".cpp", ".cxx"],
                "exclude_roots": ["build", "termin-app/install"],
                "exclude_directory_names": ["__pycache__"],
            },
            "suite_defaults": {
                "pytest": {
                    "profiles": ["pr"],
                    "platforms": ["linux"],
                }
            },
            "profiles": [
                {
                    "id": "pr",
                    "description": "PR tests",
                    "pytest_mark_expression": "not full",
                }
            ],
            "suites": [
                {
                    "id": "alpha-python",
                    "module": "alpha",
                    "executor": "pytest",
                    "roots": ["alpha/tests"],
                }
            ],
        },
    )
    _write_json(
        tmp_path / "build-system" / "docs-publication.json",
        {
            "schema": 1,
            "inventory": {
                "exclude_roots": ["build"],
                "exclude_directory_names": [".git", "__pycache__"],
            },
            "public_sites": [],
            "internal_roots": [],
        },
    )
    _write_json(
        tmp_path / "build-system" / "repository-policies.json",
        {
            "schema": 1,
            "source_size": {
                "threshold": 2000,
                "extensions": [".py", ".cpp"],
                "exclude_roots": ["build", "termin-app/install"],
            },
        },
    )
    return tmp_path


def _add_process_smoke_suite(
    repo: Path,
    *,
    profile: str,
    platform: str,
    root: str,
    capability: str,
) -> Path:
    manifest = repo / repository_control.TEST_MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["profiles"].append({"id": profile, "description": "Process smoke"})
    data["suite_defaults"]["process-smoke"] = {
        "profiles": [profile],
        "platforms": [platform],
        "required_capabilities": [capability],
    }
    data["suites"].append(
        {
            "id": "alpha-process-smoke",
            "module": "alpha",
            "executor": "process-smoke",
            "roots": [root],
            "reason": "Exercises the process boundary.",
        }
    )
    _write_json(manifest, data)
    command = repo / root
    command.parent.mkdir(parents=True, exist_ok=True)
    command.write_text("exit 0\n", encoding="utf-8")
    command.chmod(0o755)
    return command


def _add_ctest_suite(repo: Path) -> None:
    manifest = repo / repository_control.TEST_MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["suite_defaults"]["ctest"] = {
        "profiles": ["pr"],
        "platforms": ["linux"],
    }
    data["suites"].append(
        {
            "id": "alpha-native",
            "module": "alpha",
            "executor": "ctest",
            "roots": ["alpha/tests"],
        }
    )
    _write_json(manifest, data)


def test_catalog_joins_python_packages_to_test_suites(tmp_path: Path) -> None:
    repo = _repository(tmp_path)

    catalog = repository_control.load_catalog(repo)

    assert catalog.modules == (
        repository_control.ModuleEntry(
            id="alpha",
            path="alpha",
            kinds=("python",),
            python_distribution="alpha-dist",
        ),
    )
    assert catalog.documentation.sites == ()
    assert catalog.profiles[0].pytest_mark_expression == "not full"
    assert repository_control.validate_catalog(repo, catalog) == []
    assert "required_capabilities" not in repository_control.build_plan(
        catalog, "pr", "linux"
    )["suites"][0]


@pytest.mark.parametrize("field", ["environment", "capabilities"])
@pytest.mark.parametrize("location", ["defaults", "suite"])
def test_catalog_rejects_removed_suite_planning_fields(
    tmp_path: Path, field: str, location: str
) -> None:
    repo = _repository(tmp_path)
    manifest = repo / repository_control.TEST_MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    target = (
        data["suite_defaults"]["pytest"]
        if location == "defaults"
        else data["suites"][0]
    )
    target[field] = [] if field == "capabilities" else "legacy-environment"
    _write_json(manifest, data)

    with pytest.raises(
        repository_control.ManifestError,
        match=rf"unknown field: {field}",
    ):
        repository_control.load_catalog(repo)


def test_catalog_rejects_unknown_module_and_profile(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    manifest = repo / repository_control.TEST_MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["suites"][0]["module"] = "missing"
    data["suites"][0]["profiles"] = ["nightly"]
    _write_json(manifest, data)

    errors = repository_control.validate_catalog(
        repo, repository_control.load_catalog(repo)
    )

    assert "alpha-python: unknown module: missing" in errors
    assert "alpha-python: unknown profile: nightly" in errors


def test_catalog_rejects_duplicate_module_identity(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    manifest = repo / repository_control.MODULE_MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["modules"] = [
        {"id": "alpha", "path": "other-alpha", "kinds": ["cmake"]}
    ]
    (repo / "other-alpha").mkdir()
    _write_json(manifest, data)

    errors = repository_control.validate_catalog(
        repo, repository_control.load_catalog(repo)
    )

    assert errors == ["duplicate module id: alpha"]


def test_catalog_rejects_paths_outside_repository(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    manifest = repo / repository_control.TEST_MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["suites"][0]["roots"] = ["../external-tests"]
    _write_json(manifest, data)

    errors = repository_control.validate_catalog(
        repo, repository_control.load_catalog(repo)
    )

    assert errors == [
        "alpha-python: test root must be repository-relative: ../external-tests"
    ]


def test_catalog_rejects_orphan_python_test(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    orphan = repo / "unowned" / "tests" / "test_orphan.py"
    orphan.parent.mkdir(parents=True)
    orphan.write_text("def test_orphan(): pass\n", encoding="utf-8")

    errors = repository_control.validate_catalog(
        repo, repository_control.load_catalog(repo)
    )

    assert errors == ["orphan Python test: unowned/tests/test_orphan.py"]


def test_catalog_rejects_orphan_documentation_root(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    docs = repo / "alpha" / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Alpha\n", encoding="utf-8")

    errors = repository_control.validate_catalog(
        repo, repository_control.load_catalog(repo)
    )

    assert errors == ["orphan documentation root: alpha/docs"]


def test_docs_plan_uses_module_identity_and_publication_path(
    tmp_path: Path, capsys
) -> None:
    repo = _repository(tmp_path)
    docs = repo / "alpha" / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Alpha\n", encoding="utf-8")
    config = repo / "alpha" / "mkdocs.yml"
    config.write_text("site_name: Alpha\n", encoding="utf-8")
    manifest = repo / repository_control.DOCS_MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["public_sites"] = [
        {
            "module": "alpha",
            "root": "alpha/docs",
            "config": "alpha/mkdocs.yml",
            "site_path": "alpha",
        }
    ]
    _write_json(manifest, data)

    result = repository_control._cmd_docs_plan(repo, json_output=False)

    assert result == 0
    assert capsys.readouterr().out == "alpha\talpha/mkdocs.yml\talpha\n"


def test_catalog_rejects_multiple_python_test_owners(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    test_file = repo / "alpha" / "tests" / "test_alpha.py"
    test_file.write_text("def test_alpha(): pass\n", encoding="utf-8")
    manifest = repo / repository_control.TEST_MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["suites"].append(
        {
            "id": "alpha-specific",
            "module": "alpha",
            "executor": "pytest",
            "roots": ["alpha/tests/test_alpha.py"],
        }
    )
    _write_json(manifest, data)

    errors = repository_control.validate_catalog(
        repo, repository_control.load_catalog(repo)
    )

    assert errors == [
        "Python test has multiple suite owners: alpha/tests/test_alpha.py: "
        "alpha-python, alpha-specific"
    ]


def test_test_discovery_ignores_generated_build_and_install_trees(
    tmp_path: Path,
) -> None:
    repo = _repository(tmp_path)
    ignored_python_tests = (
        repo / "build" / "tests" / "test_generated.py",
        repo
        / "termin-app"
        / "install"
        / "lib"
        / "python3.10"
        / "site-packages"
        / "numpy"
        / "tests"
        / "test_generated.py",
    )
    for ignored in ignored_python_tests:
        ignored.parent.mkdir(parents=True, exist_ok=True)
        ignored.write_text("def test_generated(): pass\n", encoding="utf-8")
    ignored_native = repo / "termin-app" / "install" / "tests" / "test_generated.cpp"
    ignored_native.parent.mkdir(parents=True)
    ignored_native.write_text("int main() { return 0; }\n", encoding="utf-8")

    catalog = repository_control.load_catalog(repo)

    assert repository_control.discover_python_tests(
        repo, catalog.python_test_inventory
    ) == ()
    assert repository_control.discover_native_tests(
        repo, catalog.native_test_inventory
    ) == ()


def test_catalog_rejects_orphan_native_test(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    source = repo / "alpha" / "tests" / "test_native.cpp"
    source.write_text("int main() { return 0; }\n", encoding="utf-8")

    errors = repository_control.validate_catalog(
        repo, repository_control.load_catalog(repo)
    )

    assert errors == ["orphan native test: alpha/tests/test_native.cpp"]


def test_ctest_inventory_requires_standard_labels_and_registered_module(
    tmp_path: Path,
) -> None:
    repo = _repository(tmp_path)
    manifest = repo / repository_control.TEST_MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["suite_defaults"]["ctest"] = {
        "profiles": ["pr"],
        "platforms": ["linux"],
    }
    data["suites"].append(
        {
            "id": "alpha-native",
            "module": "alpha",
            "executor": "ctest",
            "roots": ["alpha/tests"],
        }
    )
    _write_json(manifest, data)
    catalog = repository_control.load_catalog(repo)

    errors = repository_control.validate_ctest_inventory(
        catalog,
        {"tests": [{"name": "alpha_test", "properties": []}]},
    )

    assert errors == [
        "CTest test alpha_test: expected one termin:module label",
        "CTest test alpha_test: expected one termin:tier label",
        "CTest test alpha_test: missing termin:capability label",
        "alpha-native: no configured CTest registration for module alpha",
    ]


def test_ctest_discovery_command_supports_multi_config_generators(tmp_path: Path) -> None:
    assert repository_control._ctest_discovery_command(tmp_path, None) == [
        "ctest",
        "--test-dir",
        str(tmp_path),
        "--show-only=json-v1",
    ]
    assert repository_control._ctest_discovery_command(tmp_path, "Release") == [
        "ctest",
        "--test-dir",
        str(tmp_path),
        "-C",
        "Release",
        "--show-only=json-v1",
    ]


def test_configured_native_sources_fall_back_to_cmake_file_api(tmp_path: Path) -> None:
    reply = tmp_path / ".cmake" / "api" / "v1" / "reply"
    reply.mkdir(parents=True)
    source_root = tmp_path / "source"
    _write_json(
        reply / "index-1.json",
        {"reply": {"codemodel-v2": {"jsonFile": "codemodel.json"}}},
    )
    _write_json(
        reply / "codemodel.json",
        {
            "paths": {"source": str(source_root)},
            "configurations": [
                {"name": "Release", "targets": [{"jsonFile": "target.json"}]}
            ],
        },
    )
    _write_json(
        reply / "target.json",
        {"sources": [{"path": "alpha/tests/test_native.cpp"}]},
    )

    assert repository_control._load_configured_native_sources(tmp_path) == [
        {"file": str(source_root / "alpha/tests/test_native.cpp")}
    ]


def test_ctest_plan_reports_capability_exclusion_reason(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    manifest = repo / repository_control.TEST_MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["suite_defaults"]["ctest"] = {
        "profiles": ["pr"],
        "platforms": ["linux"],
    }
    data["suites"].append(
        {
            "id": "alpha-native",
            "module": "alpha",
            "executor": "ctest",
            "roots": ["alpha/tests"],
        }
    )
    _write_json(manifest, data)
    catalog = repository_control.load_catalog(repo)
    ctest_payload = {
        "tests": [
            {
                "name": "alpha_vulkan_test",
                "properties": [
                    {
                        "name": "LABELS",
                        "value": [
                            "termin:module:alpha",
                            "termin:tier:pr",
                            "termin:capability:host",
                            "termin:capability:vulkan",
                        ],
                    }
                ],
            }
        ]
    }

    plan = repository_control.build_ctest_execution_plan(
        catalog, ctest_payload, "pr", "linux", ("host",)
    )

    assert plan["selected"] == []
    assert plan["skipped"] == [
        {
            "name": "alpha_vulkan_test",
            "suite_id": "alpha-native",
            "module": "alpha",
            "capabilities": ["host", "vulkan"],
            "reason": "missing capabilities: vulkan",
        }
    ]


def test_native_compile_inventory_rejects_source_outside_cmake_graph(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    source = repo / "alpha" / "tests" / "test_native.cpp"
    source.write_text("int main() { return 0; }\n", encoding="utf-8")
    manifest = repo / repository_control.TEST_MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["suite_defaults"]["ctest"] = {
        "profiles": ["pr"],
        "platforms": ["linux"],
    }
    data["suites"].append(
        {"id": "alpha-native", "module": "alpha", "executor": "ctest", "roots": ["alpha/tests"]}
    )
    _write_json(manifest, data)
    catalog = repository_control.load_catalog(repo)

    errors = repository_control.validate_native_compile_inventory(
        repo, catalog, [], "pr", ()
    )

    assert errors == [
        "native test source is absent from configured CMake graph: alpha/tests/test_native.cpp"
    ]


def test_plan_filters_by_profile_and_platform(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    catalog = repository_control.load_catalog(repo)

    linux_plan = repository_control.build_plan(catalog, "pr", "linux")
    windows_plan = repository_control.build_plan(catalog, "pr", "windows")

    assert [suite["id"] for suite in linux_plan["suites"]] == ["alpha-python"]
    assert windows_plan["suites"] == []
    assert windows_plan["inapplicable"] == [
        {
            "id": "alpha-python",
            "module": "alpha",
            "executor": "pytest",
            "reason": "platform 'windows' is not in declared platforms: linux",
        }
    ]


def test_cli_emits_stable_json_plan(tmp_path: Path, capsys) -> None:
    repo = _repository(tmp_path)

    result = repository_control.main(
        ["--repo-root", str(repo), "plan", "pr", "--platform", "linux", "--json"]
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["schema"] == 1
    assert output["kind"] == "termin-test-expected"
    assert output["profile"] == "pr"
    assert output["platform"] == "linux"
    assert len(output["fingerprint"]) == 64
    assert [suite["id"] for suite in output["suites"]] == ["alpha-python"]
    assert output["inapplicable"] == []


def test_plan_reports_profile_and_platform_exclusions(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    manifest = repo / repository_control.TEST_MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["profiles"].append(
        {
            "id": "nightly",
            "description": "Nightly tests",
            "pytest_mark_expression": None,
        }
    )
    data["suites"][0]["profiles"] = ["nightly"]
    _write_json(manifest, data)

    plan = repository_control.build_plan(
        repository_control.load_catalog(repo), "pr", "windows"
    )

    assert plan["suites"] == []
    assert plan["inapplicable"][0]["reason"] == (
        "profile 'pr' is not in declared profiles: nightly; "
        "platform 'windows' is not in declared platforms: linux"
    )


def test_native_source_exclusion_requires_reason(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    source = repo / "alpha" / "tests" / "test_native.cpp"
    source.write_text("int main() { return 0; }\n", encoding="utf-8")
    manifest = repo / repository_control.TEST_MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["native_test_inventory"]["source_classifications"] = [
        {
            "path": "alpha/tests/test_native.cpp",
            "profiles": ["pr"],
            "capabilities": ["window"],
            "reason": "",
        }
    ]
    _write_json(manifest, data)

    with pytest.raises(
        repository_control.ManifestError,
        match="source_classifications\\[0\\]: reason must be a non-empty string",
    ):
        repository_control.load_catalog(repo)


def test_cli_logs_manifest_errors(tmp_path: Path, capsys) -> None:
    repo = _repository(tmp_path)
    (repo / "alpha" / "tests").rmdir()

    result = repository_control.main(["--repo-root", str(repo), "check"])

    assert result == 1
    assert (
        "ERROR: alpha-python: test root does not exist: alpha/tests"
        in capsys.readouterr().err
    )


def test_check_profile_enforces_source_size_policy(tmp_path: Path, capsys) -> None:
    repo = _repository(tmp_path)
    policy_path = repo / "build-system" / "repository-policies.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["source_size"]["threshold"] = 3
    _write_json(policy_path, policy)
    (repo / "alpha" / "oversized.py").write_text("one\ntwo\nthree\n", encoding="utf-8")

    result = repository_control.main(["--repo-root", str(repo), "check"])

    assert result == 1
    assert "source-size policy violation: alpha/oversized.py: 3 lines" in (
        capsys.readouterr().err
    )


def test_check_ignores_sources_in_generated_install_tree(
    tmp_path: Path, capsys
) -> None:
    repo = _repository(tmp_path)
    policy_path = repo / "build-system" / "repository-policies.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["source_size"]["threshold"] = 3
    _write_json(policy_path, policy)
    generated = (
        repo
        / "termin-app"
        / "install"
        / "lib"
        / "python3.10"
        / "site-packages"
        / "vendor"
        / "oversized.py"
    )
    generated.parent.mkdir(parents=True)
    generated.write_text("one\ntwo\nthree\n", encoding="utf-8")

    result = repository_control.main(["--repo-root", str(repo), "check"])

    assert result == 0
    assert capsys.readouterr().err == ""


def test_run_executes_manifest_pytest_suites(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    repo = _repository(tmp_path)
    calls = []

    class FakeProcess:
        stdout = StringIO("1 passed\n")

        def wait(self) -> int:
            return 0

    def fake_popen(command, *, cwd, env, stdout, stderr, text, bufsize):
        calls.append((command, cwd, env, stdout, stderr, text, bufsize))
        return FakeProcess()

    monkeypatch.setattr(repository_control.subprocess, "Popen", fake_popen)

    result = repository_control.main(
        [
            "--repo-root",
            str(repo),
            "run",
            "pr",
            "--platform",
            "linux",
            "--python",
            "/test/python",
        ]
    )

    assert result == 0
    assert len(calls) == 1
    command, cwd, environment, stdout, stderr, text, bufsize = calls[0]
    assert command[:7] == [
        "/test/python",
        "-m",
        "pytest",
        "-m",
        "not full",
        "alpha/tests",
        "--basetemp",
    ]
    assert cwd == repo
    assert environment["TMPDIR"].startswith(str(repo / "build" / "pt"))
    assert stdout is repository_control.subprocess.PIPE
    assert stderr is repository_control.subprocess.STDOUT
    assert text is True
    assert bufsize == 1
    assert "Pytest suites: 1" in capsys.readouterr().out


def test_run_accumulates_suite_failures(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = _repository(tmp_path)

    class FakeProcess:
        stdout = StringIO("pytest failed\n")

        def wait(self) -> int:
            return 3

    def fake_popen(command, *, cwd, env, stdout, stderr, text, bufsize):
        return FakeProcess()

    monkeypatch.setattr(repository_control.subprocess, "Popen", fake_popen)

    result = repository_control.main(
        ["--repo-root", str(repo), "run", "pr", "--platform", "linux"]
    )

    assert result == 1
    assert "  - alpha-python" in capsys.readouterr().err


def test_run_fails_when_pytest_emits_nanobind_shutdown_diagnostic(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    repo = _repository(tmp_path)

    class FakeProcess:
        stdout = StringIO(
            "1 passed\n"
            "nanobind: leaked 1 instances!\n"
            " - leaked instance 0x1234\n"
        )

        def wait(self) -> int:
            return 0

    def fake_popen(command, *, cwd, env, stdout, stderr, text, bufsize):
        return FakeProcess()

    monkeypatch.setattr(repository_control.subprocess, "Popen", fake_popen)

    result = repository_control.main(
        ["--repo-root", str(repo), "run", "pr", "--platform", "linux"]
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "nanobind shutdown leak diagnostics" in captured.err
    assert "nanobind: leaked 1 instances!" in captured.err
    assert "  - alpha-python" in captured.err


def test_run_executes_manifest_process_smoke(tmp_path: Path, monkeypatch) -> None:
    repo = _repository(tmp_path)
    manifest = repo / repository_control.TEST_MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["profiles"].append(
        {
            "id": "editor-smoke",
            "description": "Editor process smoke",
        }
    )
    data["suite_defaults"]["process-smoke"] = {
        "profiles": ["editor-smoke"],
        "platforms": ["linux"],
        "required_capabilities": ["editor"],
    }
    data["suites"].append(
        {
            "id": "alpha-editor-smoke",
            "module": "alpha",
            "executor": "process-smoke",
            "roots": ["scripts/smoke"],
            "reason": "Exercises the editor process boundary.",
        }
    )
    _write_json(manifest, data)
    command = repo / "scripts" / "smoke"
    command.parent.mkdir()
    command.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    command.chmod(0o755)
    report_path = repo / "build" / "process-execution.json"
    calls = []

    def fake_run(
        args,
        *,
        cwd,
        env,
        check,
        stdout,
        stderr,
        text,
        timeout,
    ):
        calls.append((args, cwd, check, env, timeout))
        return type("Result", (), {"returncode": 0, "stdout": "ok\n"})()

    monkeypatch.setattr(process_smoke.subprocess, "run", fake_run)

    result = repository_control.main(
        [
            "--repo-root",
            str(repo),
            "run",
            "editor-smoke",
            "--platform",
            "linux",
            "--capability",
            "editor",
            "--report-output",
            str(report_path),
        ]
    )

    assert result == 0
    assert calls[0][:3] == ([str(command)], repo, False)
    assert calls[0][4] == 900.0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["kind"] == "termin-test-execution"
    assert report["executor"] == "process-smoke"
    assert report["selected"] == [{"id": "alpha-editor-smoke"}]
    assert report["executed"] == [{"id": "alpha-editor-smoke"}]


def test_windows_process_smoke_requires_a_supported_runner(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    _add_process_smoke_suite(
        repo,
        profile="windows-smoke",
        platform="windows",
        root="scripts/posix-smoke",
        capability="d3d11",
    )

    errors = repository_control.validate_catalog(
        repo, repository_control.load_catalog(repo)
    )

    assert errors == [
        "alpha-process-smoke: Windows process-smoke root has no supported runner: "
        "scripts/posix-smoke"
    ]


def test_windows_process_smoke_executes_from_canonical_plan(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    repo = _repository(tmp_path)
    command = _add_process_smoke_suite(
        repo,
        profile="windows-smoke",
        platform="windows",
        root="scripts/smoke.ps1",
        capability="d3d11",
    )
    catalog = repository_control.load_catalog(repo)
    expected = repository_control.build_plan(catalog, "windows-smoke", "windows")
    plan_path = repo / "build" / "windows-plan.json"
    report_path = repo / "build" / "process-execution.json"
    log_dir = repo / "build" / "process-logs"
    _write_json(plan_path, expected)
    calls = []

    monkeypatch.setattr(process_smoke.shutil, "which", lambda name: "pwsh.exe")

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return type("Result", (), {"returncode": 0, "stdout": "windows ok\n"})()

    monkeypatch.setattr(process_smoke.subprocess, "run", fake_run)

    result = repository_control.main(
        [
            "--repo-root",
            str(repo),
            "run",
            "windows-smoke",
            "--platform",
            "windows",
            "--executor",
            "process-smoke",
            "--capability",
            "d3d11",
            "--configuration",
            "Debug",
            "--process-timeout",
            "12",
            "--process-log-dir",
            str(log_dir),
            "--report-output",
            str(report_path),
        ]
    )

    assert result == 0
    assert calls[0][0] == ["pwsh.exe", "-NoProfile", "-File", str(command)]
    assert calls[0][1]["env"]["TERMIN_TEST_CONFIGURATION"] == "Debug"
    assert calls[0][1]["timeout"] == 12.0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["executed"] == [{"id": "alpha-process-smoke"}]
    assert report["details"]["logs"] == {
        "alpha-process-smoke": "build/process-logs/alpha-process-smoke.log"
    }
    assert repository_control._cmd_verify_suite_execution(
        plan_path, report_path, "process-smoke"
    ) == 0
    capsys.readouterr()


def test_process_smoke_missing_capability_is_an_explicit_skip(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    _add_process_smoke_suite(
        repo,
        profile="windows-smoke",
        platform="windows",
        root="scripts/smoke.ps1",
        capability="d3d11",
    )
    catalog = repository_control.load_catalog(repo)

    result = repository_control.run_process_smoke_plan(
        repo, catalog, "windows-smoke", "windows"
    )

    assert result.exit_code == 0
    assert result.executed == ()
    assert result.skipped == {
        "alpha-process-smoke": "missing capabilities: d3d11"
    }


def test_process_smoke_timeout_fails_and_retains_log(
    tmp_path: Path, monkeypatch
) -> None:
    repo = _repository(tmp_path)
    _add_process_smoke_suite(
        repo,
        profile="editor-smoke",
        platform="linux",
        root="scripts/smoke",
        capability="editor",
    )
    catalog = repository_control.load_catalog(repo)

    def timeout(*_args, **_kwargs):
        raise process_smoke.subprocess.TimeoutExpired(
            ["scripts/smoke"], 3.0, output="partial output\n"
        )

    monkeypatch.setattr(process_smoke.subprocess, "run", timeout)

    result = repository_control.run_process_smoke_plan(
        repo,
        catalog,
        "editor-smoke",
        "linux",
        capabilities=("editor",),
        timeout_seconds=3.0,
    )

    assert result.exit_code == 1
    assert "timed out after 3s" in result.failed["alpha-process-smoke"]
    log_path = repo / result.logs["alpha-process-smoke"]
    assert "partial output" in log_path.read_text(encoding="utf-8")


def test_ctest_report_records_selected_executed_and_skipped(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    _add_ctest_suite(repo)
    selection = repo / "selection.json"
    junit = repo / "ctest.xml"
    output = repo / "execution.json"
    _write_json(
        selection,
        {
            "schema": 1,
            "profile": "pr",
            "platform": "linux",
            "configuration": "Release",
            "capabilities": ["host"],
            "selected": [
                {
                    "name": "passes",
                    "suite_id": "alpha-native",
                    "module": "alpha",
                    "capabilities": ["host"],
                },
                {
                    "name": "runtime_skip",
                    "suite_id": "alpha-native",
                    "module": "alpha",
                    "capabilities": ["host"],
                },
            ],
            "skipped": [
                {
                    "name": "missing_capability",
                    "suite_id": "alpha-native",
                    "module": "alpha",
                    "reason": "missing capabilities: vulkan",
                }
            ],
        },
    )
    junit.write_text(
        "<testsuites><testsuite>"
        '<testcase name="passes" />'
        '<testcase name="runtime_skip"><skipped /></testcase>'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )

    result = repository_control._cmd_report_ctest(repo, selection, junit, output)

    assert result == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["kind"] == "termin-test-execution"
    assert report["executor"] == "ctest"
    assert report["selected"] == [{"id": "alpha-native"}]
    assert report["executed"] == [{"id": "alpha-native"}]
    assert report["skipped"] == []
    assert [
        entry["name"] for entry in report["details"]["registrations"]["skipped"]
    ] == [
        "missing_capability",
        "runtime_skip",
    ]
    assert report["failed"] == []
    assert report["details"]["configuration"] == "Release"


def test_verify_suite_execution_requires_exact_executor_coverage(
    tmp_path: Path, capsys
) -> None:
    plan = tmp_path / "plan.json"
    manifest = tmp_path / "process.json"
    expected = repository_control.build_expected_manifest(
        "sdk-installed",
        "linux",
        [
            {
                "id": "installed-smoke",
                "executor": "process-smoke",
                "module": "alpha",
            },
            {"id": "alpha-python", "executor": "pytest", "module": "alpha"},
        ],
        [],
    )
    execution = repository_control.build_execution_manifest(
        expected,
        "process-smoke",
        selected=["installed-smoke"],
        executed=["installed-smoke"],
        skipped={},
        failed={},
    )
    _write_json(plan, expected)
    _write_json(manifest, execution)

    result = repository_control._cmd_verify_suite_execution(
        plan, manifest, "process-smoke"
    )

    assert result == 0
    assert json.loads(capsys.readouterr().out)["success"] is True

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["executed"] = []
    _write_json(manifest, payload)

    result = repository_control._cmd_verify_suite_execution(
        plan, manifest, "process-smoke"
    )

    assert result == 1
    assert json.loads(capsys.readouterr().out)["missing"] == ["installed-smoke"]
