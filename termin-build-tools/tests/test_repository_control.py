from __future__ import annotations

import json
from pathlib import Path

from termin_build import repository_control


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
                "exclude_roots": ["build"],
                "exclude_directory_names": ["__pycache__"],
            },
            "suite_defaults": {
                "pytest": {
                    "profiles": ["pr"],
                    "environment": "bootstrap-python",
                    "platforms": ["linux"],
                    "capabilities": [],
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
    return tmp_path


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
    assert catalog.profiles[0].pytest_mark_expression == "not full"
    assert repository_control.validate_catalog(repo, catalog) == []


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
    data["suites"][0]["capabilities"] = []
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


def test_python_test_discovery_honors_declared_exclusions(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    ignored = repo / "build" / "tests" / "test_generated.py"
    ignored.parent.mkdir(parents=True)
    ignored.write_text("def test_generated(): pass\n", encoding="utf-8")

    catalog = repository_control.load_catalog(repo)

    assert repository_control.discover_python_tests(
        repo, catalog.python_test_inventory
    ) == ()


def test_plan_filters_by_profile_and_platform(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    catalog = repository_control.load_catalog(repo)

    linux_plan = repository_control.build_plan(catalog, "pr", "linux")
    windows_plan = repository_control.build_plan(catalog, "pr", "windows")

    assert [suite["id"] for suite in linux_plan["suites"]] == ["alpha-python"]
    assert windows_plan["suites"] == []


def test_cli_emits_stable_json_plan(tmp_path: Path, capsys) -> None:
    repo = _repository(tmp_path)

    result = repository_control.main(
        ["--repo-root", str(repo), "plan", "pr", "--platform", "linux", "--json"]
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["schema"] == 1
    assert output["profile"] == "pr"
    assert output["platform"] == "linux"
    assert [suite["id"] for suite in output["suites"]] == ["alpha-python"]


def test_cli_logs_manifest_errors(tmp_path: Path, capsys) -> None:
    repo = _repository(tmp_path)
    (repo / "alpha" / "tests").rmdir()

    result = repository_control.main(["--repo-root", str(repo), "check"])

    assert result == 1
    assert (
        "ERROR: alpha-python: test root does not exist: alpha/tests"
        in capsys.readouterr().err
    )


def test_run_executes_manifest_pytest_suites(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    repo = _repository(tmp_path)
    calls = []

    def fake_run(command, *, cwd, env, check):
        calls.append((command, cwd, env, check))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(repository_control.subprocess, "run", fake_run)

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
    command, cwd, environment, check = calls[0]
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
    assert environment["TMPDIR"].startswith(str(repo / "build" / "pytest-temp"))
    assert check is False
    assert "Pytest suites: 1" in capsys.readouterr().out


def test_run_accumulates_suite_failures(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = _repository(tmp_path)

    def fake_run(command, *, cwd, env, check):
        return type("Result", (), {"returncode": 3})()

    monkeypatch.setattr(repository_control.subprocess, "run", fake_run)

    result = repository_control.main(
        ["--repo-root", str(repo), "run", "pr", "--platform", "linux"]
    )

    assert result == 1
    assert "  - alpha-python" in capsys.readouterr().err
