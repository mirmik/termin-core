from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from termin_build import repository_control
from termin_build.execution_manifest import (
    TestExecutionContractError,
    build_execution_manifest,
    build_expected_manifest,
    validate_expected_manifest,
    verify_execution_manifests,
)


def _expected() -> dict[str, object]:
    return build_expected_manifest(
        "pr",
        "linux",
        [
            {"id": "python", "module": "alpha", "executor": "pytest"},
            {"id": "native", "module": "alpha", "executor": "ctest"},
        ],
        [
            {
                "id": "windows-smoke",
                "module": "alpha",
                "executor": "process-smoke",
                "reason": "platform 'linux' is not in declared platforms: windows",
            }
        ],
    )


def test_expected_manifest_is_deterministic_and_detects_tampering() -> None:
    first = _expected()
    second = _expected()

    assert first == second
    assert first["kind"] == "termin-test-expected"
    assert len(first["fingerprint"]) == 64

    tampered = copy.deepcopy(first)
    tampered["suites"][0]["module"] = "other"
    with pytest.raises(
        TestExecutionContractError,
        match="fingerprint does not match",
    ):
        validate_expected_manifest(tampered)


def test_inapplicable_suite_requires_a_reason() -> None:
    with pytest.raises(
        TestExecutionContractError,
        match="inapplicable suite windows-smoke reason",
    ):
        build_expected_manifest(
            "pr",
            "linux",
            [],
            [
                {
                    "id": "windows-smoke",
                    "module": "alpha",
                    "executor": "process-smoke",
                }
            ],
        )


def test_verifier_combines_independent_executor_manifests() -> None:
    expected = _expected()
    pytest_manifest = build_execution_manifest(
        expected,
        "pytest",
        selected=["python"],
        executed=["python"],
        skipped={},
        failed={},
    )
    ctest_manifest = build_execution_manifest(
        expected,
        "ctest",
        selected=["native"],
        executed=[],
        skipped={"native": "window capability is unavailable"},
        failed={},
    )

    report = verify_execution_manifests(
        expected, [pytest_manifest, ctest_manifest]
    )

    assert report["success"] is True
    assert report["executed"] == ["python"]
    assert report["skipped"] == [
        {"id": "native", "reason": "window capability is unavailable"}
    ]
    assert report["missing"] == []
    assert report["inapplicable"] == [
        {
            "id": "windows-smoke",
            "executor": "process-smoke",
            "reason": "platform 'linux' is not in declared platforms: windows",
        }
    ]


def test_verifier_reports_unaccounted_and_unknown_suites() -> None:
    expected = _expected()
    manifest = build_execution_manifest(
        expected,
        "pytest",
        selected=["python", "unknown"],
        executed=["unknown"],
        skipped={},
        failed={},
    )

    report = verify_execution_manifests(expected, [manifest])

    assert report["success"] is False
    assert report["missing"] == ["native", "python"]
    assert report["missing_selected"] == ["native"]
    assert report["unexpected_selected"] == ["unknown"]
    assert report["unexpected_results"] == ["unknown"]

    empty_unknown_executor = build_execution_manifest(
        expected,
        "device",
        selected=[],
        executed=[],
        skipped={},
        failed={},
    )
    report = verify_execution_manifests(expected, [empty_unknown_executor])
    assert report["success"] is False
    assert report["unexpected_executors"] == ["device"]


def test_execution_outcome_is_unique_and_skip_reason_is_required() -> None:
    expected = _expected()
    with pytest.raises(TestExecutionContractError, match="reason must be"):
        build_execution_manifest(
            expected,
            "pytest",
            selected=["python"],
            executed=[],
            skipped={"python": ""},
            failed={},
        )

    with pytest.raises(TestExecutionContractError, match="multiple outcomes"):
        build_execution_manifest(
            expected,
            "pytest",
            selected=["python"],
            executed=["python"],
            skipped={},
            failed={"python": "pytest failed"},
        )

    unknown_outcome = build_execution_manifest(
        expected,
        "pytest",
        selected=["python"],
        executed=["python"],
        skipped={},
        failed={},
    )
    unknown_outcome["cancelled"] = [{"id": "python"}]
    with pytest.raises(TestExecutionContractError, match="unknown fields: cancelled"):
        verify_execution_manifests(expected, [unknown_outcome])


def test_verify_execution_cli_reports_missing_suite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    expected = _expected()
    manifest = build_execution_manifest(
        expected,
        "pytest",
        selected=["python"],
        executed=["python"],
        skipped={},
        failed={},
    )
    expected_path = tmp_path / "expected.json"
    manifest_path = tmp_path / "pytest.json"
    expected_path.write_text(json.dumps(expected), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = repository_control.main(
        [
            "--repo-root",
            str(tmp_path),
            "verify-execution",
            "--expected",
            str(expected_path),
            "--manifest",
            str(manifest_path),
        ]
    )

    report = json.loads(capsys.readouterr().out)
    assert result == 1
    assert report["kind"] == "termin-test-verification"
    assert report["missing"] == ["native"]
