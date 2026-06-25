import os
import subprocess
import sys
from pathlib import Path


def test_import_termin_inspect_without_ld_library_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sdk_root = repo_root / "sdk"
    if not (sdk_root / "lib").is_dir():
        raise AssertionError(f"test requires built SDK lib directory: {sdk_root / 'lib'}")

    env = os.environ.copy()
    env["TERMIN_SDK"] = str(sdk_root)
    env.pop("LD_LIBRARY_PATH", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import termin.inspect; print(termin.inspect.InspectRegistry.__name__)",
        ],
        cwd=repo_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "InspectRegistry"
