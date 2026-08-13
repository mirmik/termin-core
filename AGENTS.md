# AGENTS.md

These instructions apply to the complete `termin-core` repository.

## Boundary

Termin Core must remain domain-neutral. Do not introduce dependencies on
graphics, image, mesh, shaders, assets, scenes, physics, editor, player or
engine packages. External consumers use the installed SDK only; do not add
sibling-checkout or source-tree fallbacks.

## Build and tests

- Use `task` as the public repository command interface (`task --list` shows
  the available commands). Build the complete SDK with `task build`. The
  repository has one product and no SDK profile/backend flags.
- Run tests through `task test` after initializing `termin-thirdparty/guard`.
- Python tests use `sdk/bin/termin_python` and the checkout overlay prepared by
  the internal platform launcher under `scripts/test/`.
- Validate the installed boundary and relocation with `task smoke`.

The scripts under `scripts/build/` and `scripts/test/` are implementation
details and manual fallback entrypoints. Keep Linux shell and Windows
PowerShell launchers behaviorally equivalent.

Use `apply_patch` for edits, preserve unrelated work, log failures, avoid
non-reflective `getattr`/`setattr`/`hasattr`, and do not introduce C/C++
`thread_local` state.
