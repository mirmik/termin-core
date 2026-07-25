"""Copy an installed Termin SDK and verify the relocated runtime contract."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys
import tempfile

from .sdk_verification import verify_relocated_sdk


def relocated_sdk_smoke(
    sdk_root: Path,
    *,
    destination_root: Path | None = None,
) -> int:
    source = sdk_root.resolve()
    if not source.is_dir():
        print(f"ERROR: SDK root does not exist: {source}", file=sys.stderr)
        return 1

    if destination_root is not None:
        destination = destination_root.resolve()
        if destination.exists():
            print(
                f"ERROR: relocation destination already exists: {destination}",
                file=sys.stderr,
            )
            return 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, symlinks=False)
        print(f"Relocated SDK: {source} -> {destination}")
        return verify_relocated_sdk(destination)

    with tempfile.TemporaryDirectory(prefix="termin-relocated-sdk-") as temp_dir:
        destination = Path(temp_dir) / "sdk"
        shutil.copytree(source, destination, symlinks=False)
        print(f"Relocated SDK: {source} -> {destination}")
        return verify_relocated_sdk(destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sdk-root",
        type=Path,
        required=True,
        help="Installed SDK tree to copy and verify.",
    )
    parser.add_argument(
        "--destination-root",
        type=Path,
        default=None,
        help="Keep the relocated copy at this new path instead of using a temporary tree.",
    )
    args = parser.parse_args(argv)
    return relocated_sdk_smoke(
        args.sdk_root,
        destination_root=args.destination_root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
