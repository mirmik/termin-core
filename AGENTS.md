# AGENTS.md

These instructions apply to the complete `termin-core` repository.

## Boundary

Termin Core must remain domain-neutral. Do not introduce dependencies on
graphics, image, mesh, shaders, assets, scenes, physics, editor, player or
engine packages. External consumers use the installed SDK only; do not add
sibling-checkout or source-tree fallbacks.

## Build and tests

- Build the complete SDK with `./build-sdk.sh` (PowerShell equivalent on
  Windows). The repository has one product and no SDK profile/backend flags.
- Run tests through `./run-tests.sh` after initializing
  `termin-thirdparty/guard`.
- Python tests use `sdk/bin/termin_python` and the checkout overlay prepared by
  `./setup-sdk-python-env.sh`.
- Validate the installed boundary with
  `scripts/smoke-installed-core-consumers` and the relocated SDK smoke.

Use `apply_patch` for edits, preserve unrelated work, log failures, avoid
non-reflective `getattr`/`setattr`/`hasattr`, and do not introduce C/C++
`thread_local` state.
