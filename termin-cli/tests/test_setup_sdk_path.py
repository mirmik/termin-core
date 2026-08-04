from __future__ import annotations

import os
from pathlib import Path
import subprocess


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPOSITORY_ROOT / "setup-sdk-path.sh"


def _run_installer(home: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment.pop("TERMIN_BASHRC", None)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_setup_sdk_path_is_idempotent_and_preserves_bashrc(tmp_path):
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text("# user configuration\n", encoding="utf-8")

    first = _run_installer(tmp_path)
    first_contents = bashrc.read_text(encoding="utf-8")
    second = _run_installer(tmp_path)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert bashrc.read_text(encoding="utf-8") == first_contents
    assert first_contents.startswith("# user configuration\n")
    assert first_contents.count("# >>> Termin SDK PATH >>>") == 1
    assert first_contents.count(str(REPOSITORY_ROOT / "sdk" / "bin")) == 2


def test_setup_sdk_path_makes_termin_bin_visible(tmp_path):
    result = _run_installer(tmp_path)
    assert result.returncode == 0, result.stderr

    shell = subprocess.run(
        [
            "bash",
            "--noprofile",
            "--norc",
            "-c",
            'PATH=/usr/bin:/bin; source "$1"; printf "%s" "$PATH"',
            "bash",
            str(tmp_path / ".bashrc"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert shell.stdout.split(":", 1)[0] == str(REPOSITORY_ROOT / "sdk" / "bin")


def test_setup_sdk_path_rejects_malformed_managed_block(tmp_path):
    bashrc = tmp_path / ".bashrc"
    original = "# >>> Termin SDK PATH >>>\nunterminated\n"
    bashrc.write_text(original, encoding="utf-8")

    result = _run_installer(tmp_path)

    assert result.returncode == 1
    assert "malformed Termin SDK PATH block" in result.stderr
    assert bashrc.read_text(encoding="utf-8") == original
