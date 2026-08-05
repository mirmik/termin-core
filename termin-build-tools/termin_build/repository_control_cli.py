"""Argument parser for the repository control command line."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Collection
from pathlib import Path


def build_parser(
    supported_platforms: Collection[str],
    supported_executors: Collection[str],
    host_platform: Callable[[], str],
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Repository module catalog and test execution planner."
    )
    parser.add_argument("--repo-root", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check", help="Validate repository control manifests.")

    list_parser = subparsers.add_parser("list", help="List catalog entries.")
    list_parser.add_argument("subject", choices=("modules", "profiles", "suites"))
    list_parser.add_argument("--json", action="store_true", dest="json_output")

    docs_plan_parser = subparsers.add_parser(
        "docs-plan", help="Emit the manifest-driven documentation publication plan."
    )
    docs_plan_parser.add_argument("--json", action="store_true", dest="json_output")

    plan_parser = subparsers.add_parser(
        "plan", help="Build the canonical expected coverage manifest."
    )
    plan_parser.add_argument("profile")
    plan_parser.add_argument("--platform", choices=sorted(supported_platforms))
    plan_parser.add_argument("--json", action="store_true", dest="json_output")

    ctest_parser = subparsers.add_parser(
        "check-ctest", help="Validate configured CTest labels and native inventory."
    )
    ctest_parser.add_argument("--build-dir", type=Path, required=True)
    ctest_parser.add_argument("--profile", required=True)
    ctest_parser.add_argument("--capability", action="append", default=[])
    ctest_parser.add_argument(
        "--config", help="CTest multi-config configuration, for example Release."
    )

    ctest_plan_parser = subparsers.add_parser(
        "ctest-plan", help="Select configured CTest registrations from the planner."
    )
    ctest_plan_parser.add_argument("--build-dir", type=Path, required=True)
    ctest_plan_parser.add_argument("--profile", required=True)
    ctest_plan_parser.add_argument(
        "--platform",
        choices=sorted(supported_platforms),
        default=host_platform(),
    )
    ctest_plan_parser.add_argument("--capability", action="append", default=[])
    ctest_plan_parser.add_argument("--json", action="store_true", dest="json_output")
    ctest_plan_parser.add_argument("--regex", action="store_true", dest="regex_output")
    ctest_plan_parser.add_argument(
        "--build-targets",
        action="store_true",
        dest="build_targets_output",
        help="Emit the exact CMake executable targets selected by the plan.",
    )
    ctest_plan_parser.add_argument(
        "--config", help="CTest multi-config configuration, for example Release."
    )

    ctest_report_parser = subparsers.add_parser(
        "report-ctest", help="Write an execution manifest from CTest JUnit output."
    )
    ctest_report_parser.add_argument("--selection", type=Path, required=True)
    ctest_report_parser.add_argument("--junit", type=Path, required=True)
    ctest_report_parser.add_argument("--output", type=Path, required=True)

    verify_suite_parser = subparsers.add_parser(
        "verify-suite-execution",
        help="Verify one executor manifest against a planner JSON.",
    )
    verify_suite_parser.add_argument("--plan", type=Path, required=True)
    verify_suite_parser.add_argument("--manifest", type=Path, required=True)
    verify_suite_parser.add_argument(
        "--executor", choices=sorted(supported_executors), required=True
    )

    verify_execution_parser = subparsers.add_parser(
        "verify-execution",
        help="Verify canonical executor manifests against expected coverage.",
    )
    verify_execution_parser.add_argument("--expected", type=Path, required=True)
    verify_execution_parser.add_argument(
        "--manifest", type=Path, action="append", default=[]
    )

    run_parser = subparsers.add_parser(
        "run", help="Execute planner-selected automatic Python suites."
    )
    run_parser.add_argument("profile")
    run_parser.add_argument("--platform", choices=sorted(supported_platforms))
    run_parser.add_argument("--python", default=sys.executable, dest="python_executable")
    run_parser.add_argument("--python-arg", action="append", default=[])
    run_parser.add_argument(
        "--executor", action="append", choices=sorted(supported_executors), default=[]
    )
    run_parser.add_argument("--report-output", type=Path)
    run_parser.add_argument("--capability", action="append", default=[])
    run_parser.add_argument("--configuration")
    run_parser.add_argument("--process-timeout", type=float, default=900.0)
    run_parser.add_argument("--process-log-dir", type=Path)
    run_parser.add_argument(
        "--pytest-jobs",
        type=int,
        default=None,
        help="Maximum concurrent pytest suites (default: TERMIN_PYTEST_JOBS or 1).",
    )
    return parser
