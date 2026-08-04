from __future__ import annotations

import json
from pathlib import Path
import subprocess


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TERMIN = REPOSITORY_ROOT / "sdk" / "bin" / "termin"


def test_installed_termin_init_routes_to_project_backend(tmp_path):
    project_dir = tmp_path / "Demo"
    project_dir.mkdir()

    result = subprocess.run(
        [str(TERMIN), "init"],
        cwd=project_dir,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    manifest = json.loads((project_dir / "Demo.terminproj").read_text(encoding="utf-8"))
    assert manifest == {"version": 1, "name": "Demo"}
    assert (project_dir / "scene.scene").is_file()
    assert (project_dir / "project_settings" / "project.json").is_file()

    repeated = subprocess.run(
        [str(TERMIN), "init"],
        cwd=project_dir,
        check=False,
        capture_output=True,
        text=True,
    )

    assert repeated.returncode == 2
    assert "already contains a .terminproj file" in repeated.stderr
