"""Canonical expected-coverage and executor-result manifest contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping


EXPECTED_KIND = "termin-test-expected"
EXECUTION_KIND = "termin-test-execution"
VERIFICATION_KIND = "termin-test-verification"
SCHEMA_VERSION = 1
_RESULT_FIELDS = ("executed", "skipped", "failed")
_EXPECTED_FIELDS = {
    "schema",
    "kind",
    "profile",
    "platform",
    "suites",
    "inapplicable",
    "fingerprint",
}
_EXECUTION_FIELDS = {
    "schema",
    "kind",
    "expected_fingerprint",
    "profile",
    "platform",
    "executor",
    "selected",
    "executed",
    "skipped",
    "failed",
    "details",
}


class TestExecutionContractError(ValueError):
    """Raised when a test coverage manifest violates the shared contract."""

    __test__ = False


def _canonical_digest(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _non_empty_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TestExecutionContractError(f"{context} must be a non-empty string")
    return value


def _object_list(payload: Mapping[str, object], field: str) -> list[dict[str, object]]:
    value = payload.get(field)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise TestExecutionContractError(f"{field} must be a list of objects")
    return value


def _validate_header(payload: Mapping[str, object], kind: str, context: str) -> None:
    if payload.get("schema") != SCHEMA_VERSION:
        raise TestExecutionContractError(
            f"{context} has unsupported schema: {payload.get('schema')!r}"
        )
    if payload.get("kind") != kind:
        raise TestExecutionContractError(
            f"{context} has unexpected kind: {payload.get('kind')!r}"
        )
    _non_empty_string(payload.get("profile"), f"{context} profile")
    _non_empty_string(payload.get("platform"), f"{context} platform")


def _reject_unknown_fields(
    payload: Mapping[str, object], allowed: set[str], context: str
) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise TestExecutionContractError(
            f"{context} has unknown fields: " + ", ".join(unknown)
        )


def build_expected_manifest(
    profile: str,
    platform: str,
    applicable: Iterable[Mapping[str, object]],
    inapplicable: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Build and validate the checkout-local expected coverage manifest."""
    payload: dict[str, object] = {
        "schema": SCHEMA_VERSION,
        "kind": EXPECTED_KIND,
        "profile": profile,
        "platform": platform,
        "suites": [dict(entry) for entry in applicable],
        "inapplicable": [dict(entry) for entry in inapplicable],
    }
    payload["fingerprint"] = _canonical_digest(payload)
    validate_expected_manifest(payload)
    return payload


def validate_expected_manifest(payload: Mapping[str, object]) -> None:
    """Validate suite identity, applicability, reasons, and fingerprint."""
    _validate_header(payload, EXPECTED_KIND, "expected manifest")
    _reject_unknown_fields(payload, _EXPECTED_FIELDS, "expected manifest")
    seen: set[str] = set()
    for field in ("suites", "inapplicable"):
        for entry in _object_list(payload, field):
            suite_id = _non_empty_string(entry.get("id"), f"{field} suite id")
            _non_empty_string(entry.get("module"), f"suite {suite_id} module")
            _non_empty_string(entry.get("executor"), f"suite {suite_id} executor")
            if suite_id in seen:
                raise TestExecutionContractError(
                    f"suite occurs more than once in expected manifest: {suite_id}"
                )
            seen.add(suite_id)
            if field == "inapplicable":
                _non_empty_string(
                    entry.get("reason"), f"inapplicable suite {suite_id} reason"
                )

    fingerprint = _non_empty_string(
        payload.get("fingerprint"), "expected manifest fingerprint"
    )
    unsigned = dict(payload)
    del unsigned["fingerprint"]
    actual = _canonical_digest(unsigned)
    if fingerprint != actual:
        raise TestExecutionContractError(
            "expected manifest fingerprint does not match its content"
        )


def build_execution_manifest(
    expected: Mapping[str, object],
    executor: str,
    *,
    selected: Iterable[str],
    executed: Iterable[str],
    skipped: Mapping[str, str],
    failed: Mapping[str, str | None],
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build one natural executor's suite-level result manifest."""
    validate_expected_manifest(expected)
    payload: dict[str, object] = {
        "schema": SCHEMA_VERSION,
        "kind": EXECUTION_KIND,
        "expected_fingerprint": expected["fingerprint"],
        "profile": expected["profile"],
        "platform": expected["platform"],
        "executor": executor,
        "selected": [{"id": suite_id} for suite_id in selected],
        "executed": [{"id": suite_id} for suite_id in executed],
        "skipped": [
            {"id": suite_id, "reason": reason}
            for suite_id, reason in skipped.items()
        ],
        "failed": [
            ({"id": suite_id, "reason": reason} if reason else {"id": suite_id})
            for suite_id, reason in failed.items()
        ],
    }
    if details is not None:
        payload["details"] = dict(details)
    validate_execution_manifest(expected, payload)
    return payload


def _entry_ids(
    payload: Mapping[str, object], field: str, *, require_reason: bool = False
) -> tuple[set[str], dict[str, str]]:
    ids: set[str] = set()
    reasons: dict[str, str] = {}
    for entry in _object_list(payload, field):
        suite_id = _non_empty_string(entry.get("id"), f"{field} suite id")
        if suite_id in ids:
            raise TestExecutionContractError(
                f"duplicate {field} entry in execution manifest: {suite_id}"
            )
        ids.add(suite_id)
        reason = entry.get("reason")
        if require_reason:
            reasons[suite_id] = _non_empty_string(
                reason, f"{field} suite {suite_id} reason"
            )
        elif reason is not None:
            reasons[suite_id] = _non_empty_string(
                reason, f"{field} suite {suite_id} reason"
            )
    return ids, reasons


def validate_execution_manifest(
    expected: Mapping[str, object], payload: Mapping[str, object]
) -> None:
    """Validate one executor manifest without deciding coverage success."""
    validate_expected_manifest(expected)
    _validate_header(payload, EXECUTION_KIND, "execution manifest")
    _reject_unknown_fields(payload, _EXECUTION_FIELDS, "execution manifest")
    executor = _non_empty_string(payload.get("executor"), "execution manifest executor")
    if payload.get("profile") != expected.get("profile"):
        raise TestExecutionContractError(
            f"{executor} execution profile does not match expected manifest"
        )
    if payload.get("platform") != expected.get("platform"):
        raise TestExecutionContractError(
            f"{executor} execution platform does not match expected manifest"
        )
    if payload.get("expected_fingerprint") != expected.get("fingerprint"):
        raise TestExecutionContractError(
            f"{executor} execution manifest targets a different expected manifest"
        )
    if "details" in payload and not isinstance(payload["details"], dict):
        raise TestExecutionContractError("execution manifest details must be an object")

    _entry_ids(payload, "selected")
    outcomes: dict[str, set[str]] = {}
    for field in _RESULT_FIELDS:
        outcomes[field], _ = _entry_ids(
            payload, field, require_reason=field == "skipped"
        )
    for left, right in (("executed", "skipped"), ("executed", "failed"), ("skipped", "failed")):
        overlap = sorted(outcomes[left] & outcomes[right])
        if overlap:
            raise TestExecutionContractError(
                f"execution suites have multiple outcomes ({left}, {right}): "
                + ", ".join(overlap)
            )


def verify_execution_manifests(
    expected: Mapping[str, object], manifests: Iterable[Mapping[str, object]]
) -> dict[str, object]:
    """Compare expected coverage with independent executor manifests."""
    validate_expected_manifest(expected)
    applicable = _object_list(expected, "suites")
    expected_by_executor: dict[str, set[str]] = {}
    for entry in applicable:
        executor = str(entry["executor"])
        expected_by_executor.setdefault(executor, set()).add(str(entry["id"]))

    observed_executors: set[str] = set()
    selected_all: set[str] = set()
    executed_all: set[str] = set()
    skipped_all: dict[str, str] = {}
    failed_all: dict[str, str | None] = {}
    unexpected_selected: set[str] = set()
    unexpected_results: set[str] = set()
    unexpected_executors: set[str] = set()

    for manifest in manifests:
        validate_execution_manifest(expected, manifest)
        executor = str(manifest["executor"])
        if executor in observed_executors:
            raise TestExecutionContractError(
                f"multiple execution manifests for executor: {executor}"
            )
        observed_executors.add(executor)
        expected_ids = expected_by_executor.get(executor, set())
        if executor not in expected_by_executor:
            unexpected_executors.add(executor)
        selected, _ = _entry_ids(manifest, "selected")
        selected_all.update(selected & expected_ids)
        unexpected_selected.update(selected - expected_ids)
        for field in _RESULT_FIELDS:
            ids, reasons = _entry_ids(
                manifest, field, require_reason=field == "skipped"
            )
            unexpected_results.update(ids - expected_ids)
            accepted = ids & expected_ids
            if field == "executed":
                executed_all.update(accepted)
            elif field == "skipped":
                skipped_all.update({suite_id: reasons[suite_id] for suite_id in accepted})
            else:
                failed_all.update(
                    {suite_id: reasons.get(suite_id) for suite_id in accepted}
                )

    expected_ids = {str(entry["id"]) for entry in applicable}
    terminal = executed_all | set(skipped_all) | set(failed_all)
    missing_selected = expected_ids - selected_all
    missing = expected_ids - terminal
    inapplicable = [
        {"id": entry["id"], "executor": entry["executor"], "reason": entry["reason"]}
        for entry in _object_list(expected, "inapplicable")
    ]
    successful = not (
        failed_all
        or missing_selected
        or missing
        or unexpected_selected
        or unexpected_results
        or unexpected_executors
    )
    return {
        "schema": SCHEMA_VERSION,
        "kind": VERIFICATION_KIND,
        "profile": expected["profile"],
        "platform": expected["platform"],
        "expected_fingerprint": expected["fingerprint"],
        "success": successful,
        "selected": sorted(selected_all),
        "executed": sorted(executed_all),
        "skipped": [
            {"id": suite_id, "reason": skipped_all[suite_id]}
            for suite_id in sorted(skipped_all)
        ],
        "failed": [
            ({"id": suite_id, "reason": failed_all[suite_id]}
             if failed_all[suite_id] else {"id": suite_id})
            for suite_id in sorted(failed_all)
        ],
        "missing": sorted(missing),
        "inapplicable": inapplicable,
        "missing_selected": sorted(missing_selected),
        "unexpected_selected": sorted(unexpected_selected),
        "unexpected_results": sorted(unexpected_results),
        "unexpected_executors": sorted(unexpected_executors),
    }


def read_manifest(path: Path, description: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TestExecutionContractError(f"{description} does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TestExecutionContractError(f"invalid {description}: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TestExecutionContractError(f"{description} root must be an object: {path}")
    return payload
