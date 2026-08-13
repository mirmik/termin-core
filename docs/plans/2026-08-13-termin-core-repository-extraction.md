# Termin Core Repository Extraction Plan

Date: 2026-08-13

Post-extraction note: the repository command interface was subsequently
consolidated under `Taskfile.yml`. References below to root build/test scripts
describe the extraction state at the time of the plan and are historical.

Canonical architecture:

- [Core SDK and domain repository boundary](../architecture/2026-08-13-core-domain-repositories.md)

Taskboard:

- #1604 - extraction umbrella;
- #1605 - canonical Core product closure;
- #1606 - generic MCP admission cleanup (parallel, not a Core v1 blocker);
- #1607 - isolated Core SDK profile;
- #1608 - generic SDK tooling split;
- #1609 - relocated installed consumers;
- #1610 - physical repository extraction;
- #1611 - graphics/full consumption of installed Core;
- #1612 - duplicated-source removal and ownership cutover.

## Goal

Create an independently buildable and distributable `termin-core` repository
and Core SDK, then make the current monorepo consume that SDK without source
fallback. This is the rehearsal and foundation for subsequent Graphics and
Physics repository extraction.

The plan favors an early physical repository boundary. It does not require
materials, glTF, skeleton/animation or physics integration to be completed
first.

## Initial delivery scope

The first Core repository contains:

- `termin-base`;
- `termin-dispatch`;
- `termin-inspect`;
- `termin-nanobind-sdk`;
- `termin-python-host`;
- the isolated launcher owned by `termin-python-host`;
- the generic subset of SDK/build tooling required to build, verify and publish
  Core;
- the canonical bundled Python runtime inputs and lock machinery;
- Core-native and Python tests;
- external CMake and Python consumer smoke fixtures.

`termin-mcp` is included in Core after its scene context moved to host adapters
and screenshot/readback support moved to the graphics-owned
`termin-graphics-mcp` distribution.

## Non-goals

- Extract Graphics, Physics or Engine in this plan.
- Promise a stable long-term binary ABI in the first release.
- Preserve source fallback from consumers to a sibling checkout.
- Move `termin-assets`, `termin-image`, `termin-mesh` or `termin-scene` into
  Core for convenience.
- Generalize every monorepo build script before a concrete Core consumer needs
  it.
- Create a repository per Core module.

## Stage 0: freeze the closure and ownership manifest

Create one machine-readable Core product manifest describing:

- native targets and their public dependencies;
- Python distributions and native extension targets;
- installed headers, CMake configs and runtime libraries;
- bundled Python/runtime inputs;
- tests, smoke consumers and owned resources;
- explicitly forbidden domain packages/artifacts.

Replace duplicated Core closure knowledge in root CMake, Python package
selection, SDK doctor and verification with projections from that manifest, or
with small repository-local declarations generated from it.

Audit public includes and Python imports for every candidate. Record exclusions
rather than introducing fallback imports to keep an attractive closure.

Exit criteria:

- the closure has no dependency on graphics, image, mesh, assets, scene,
  physics, editor or engine;
- CI/tests detect an undeclared package or target entering the closure;
- Core product ownership has one authoritative declaration.

## Stage 1: build a Core SDK inside the current repository

Add a temporary `core` SDK/build profile which builds only the frozen closure
into its own build directory and install prefix. This is scaffolding for
extraction, not a permanent third interpretation of the final Core repository.

The build must produce:

- installed libraries and headers;
- usable CMake package configs;
- bundled CPython 3.14t and the nanobind runtime/profile;
- Core wheels installed offline from an exact wheelhouse;
- a Core artifact manifest with file hashes and build identity;
- an isolated Python launcher suitable for import smoke tests.

Verification must reject forbidden domain artifacts rather than merely omit
known application payloads.

Exit criteria:

- a clean Core profile build and central Core test selection pass on Linux;
- corresponding Windows build commands and checks are present;
- the resulting SDK relocates and its manifest/hashes verify;
- `termin.image`, `tmesh`, `tgfx`, `termin.scene`, `termin.assets` and product
  hosts are absent.

## Stage 2: separate generic build tooling from product recipes

Refactor only the tooling needed for cross-repository use:

- Core-owned artifact schema and verifier;
- Core/Python runtime lock and offline installer;
- pack compatibility and collision checks;
- generic composition primitives;
- repository-local product manifest loading.

Keep graphics profile closure, shader checks, showcase rules and engine
application payload knowledge outside the shared package. Shared tooling accepts
typed manifests; it does not contain a growing switch over every Termin product.

The installed SDK carries a hash-bound resolved product contract, so release
and relocation checks do not reopen repository-local recipes. Product-owned
showcase tests live with the showcase rather than in the shared tooling suite.

Exit criteria:

- Core tooling can be packaged and tested without importing monorepo product
  modules;
- the existing full/graphics build can consume the same generic manifest and
  verification primitives;
- domain-specific rules remain in their owning repository.

## Stage 3: prove installed external consumption

Add consumers located outside the Core source tree:

1. A minimal C/C++ project using only installed `find_package()` configs and
   public headers for base, dispatch and inspect.
2. An isolated bundled-Python process importing `tcbase`, `termin.dispatch` and
   `termin.inspect` from the installed SDK.
3. A small extension fixture built with the installed nanobind profile against
   the installed Python ABI.
4. An embedding fixture using `termin-python-host`, where supported.

The smoke harness must remove source overlay variables and prevent the source
tree from appearing on `PYTHONPATH` or `CMAKE_PREFIX_PATH`.

The repository-owned command is:

```bash
./scripts/smoke-installed-core-consumers --sdk-root ./sdk-core
```

On Windows, invoke the same Python script with the installed launcher:

```powershell
sdk-core\bin\termin_python.exe scripts\smoke-installed-core-consumers --sdk-root sdk-core
```

The harness copies both SDK and fixture to a temporary tree, clears ambient
Python/CMake overlays, verifies that removing an installed package makes CMake
configuration fail, then builds and runs native, nanobind and embedded-Python
consumers.

Exit criteria:

- all fixtures configure, build and run from a copied/relocated Core SDK;
- a deliberately missing installed dependency fails instead of finding a
  source checkout;
- no fixture links or imports a build-tree artifact accidentally.

## Stage 4: extract the physical repository

Create `termin-core` by filtering the current git history for the frozen source,
tooling, tests and documentation paths. Preserve file history where practical;
do not initialize the repository as an unrelated source dump.

Give the new repository its own:

- root CMake build without `TERMIN_SDK_PROFILE`;
- `build-sdk.sh` / PowerShell equivalent;
- central test entry points;
- runtime lock and wheelhouse preparation;
- README, architecture boundary and repository instructions;
- Linux and Windows CI;
- artifact publication/versioning configuration.

Extraction must not delete the old source copy yet. From this point, however,
the new repository is prepared to become the authoritative source; the overlap
window is kept short and accepts no independent feature development in both
copies.

Exit criteria:

- a checkout containing only `termin-core` builds the same verified Core SDK;
- CI does not fetch or mount the engine/graphics monorepo sources;
- artifact manifests from the repository are reproducible for identical
  inputs, modulo explicitly documented non-deterministic metadata.

## Stage 5: consume installed Core from the current repository

Publish or stage a pinned Core SDK artifact and add an explicit Core SDK input
to the current repository build. Convert lower-layer `add_subdirectory()` uses
to installed package discovery in the graphics/full build paths.

Rules:

- one explicit Core SDK prefix/build identity;
- `find_package(... CONFIG REQUIRED)` for native packages;
- wheels/runtime metadata from the Core artifact;
- no `FetchContent`, sibling path, environment guess or source fallback;
- build failure when the required Core identity, target or Python ABI does not
  match.

During migration, targets still inside the monorepo must not accidentally make
the installed packages disappear behind same-named local targets. Add a CI mode
which renames/removes the old Core directories before configuration.

Exit criteria:

- graphics profile and full SDK build against the installed pinned Core SDK;
- central tests and graphics showcase pass in that mode;
- source-hiding CI proves there is no remaining dependency on old Core paths;
- Core headers, libraries and wheels in composed outputs come from the pinned
  artifact and have one owner.

## Stage 6: cut over source ownership

Make `termin-core` the single source of truth:

1. Freeze the final monorepo commit that still contains Core sources.
2. Pin a Core artifact built from the authoritative repository.
3. Remove duplicated Core source/tooling paths from the engine monorepo.
4. Retain only consumer configuration and integration tests.
5. Enable blocking CI against the pinned Core artifact and an early-warning
   compatibility job against Core main.
6. Document the coordinated change procedure for API changes spanning Core and
   a consumer.

Exit criteria:

- the current repository has no authoritative copy of Core source files;
- normal builds work from a fresh checkout with only the pinned Core artifact;
- a full SDK can be composed without file collisions or duplicate Python
  ownership;
- changes to Core occur only in the Core repository.

## Stage 7: admit generic MCP support

This stage may be completed before or after the physical cutover, but it has its
own acceptance gate:

- remove `termin-image` and `termin-scene` from the base `termin-mcp`
  distribution;
- inject geometry/scene/resource context from engine hosts;
- move screenshot/image encoding support to a graphics-side adapter;
- keep protocol/server/executor logic in the Core package;
- add an isolated Core-only MCP test and host-adapter tests.

After verification, add the generic package to the Core product manifest and
publish it in a subsequent Core artifact. Do not delay Core v1 merely to include
MCP.

## Required verification matrix

| Gate | Linux | Windows |
|---|---|---|
| Core native build/tests | required | required |
| Core Python wheel/import smoke | required | required |
| Relocated Core SDK | required | required |
| External CMake consumer | required | required |
| Installed nanobind extension | required | required |
| Graphics against installed Core | required | required |
| Full SDK against installed Core | required | required |
| Source-hidden consumer build | required | required |

Platform-specific failures go to `On Test` only when implementation is complete
and the named environment is the sole remaining check.

## Rollback and overlap policy

Before cutover, the monorepo copy remains recoverable through git history. After
cutover, rollback means pinning the previous verified Core artifact, not copying
sources back into the consumer repository.

The temporary duplicate-source window must be measured in migration work, not
maintained as a supported topology. Cross-cutting changes during that window are
made first in the future authoritative Core repository and consumed through a
new artifact.

## Completion criterion

The plan is complete when `termin-core` independently publishes a verified Core
SDK and the current graphics/full builds consume its pinned installed artifact
with the old Core source directories absent. At that point the same artifact
and composition contract can be reused for Graphics and later Physics
extraction.
