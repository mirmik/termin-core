# Termin Core

Termin Core is the independently buildable common foundation for Termin
domain SDKs. It owns common values and geometry, deferred dispatch, inspection
contracts, the canonical free-threaded Python runtime and nanobind ABI,
embedded-Python hosting, and process-neutral MCP support.

Core deliberately contains no graphics, image, mesh, asset, scene, physics,
editor or engine facilities. Domain repositories consume a versioned installed
Core SDK; sibling source checkouts are not a supported dependency mechanism.

## Build

The repository is one product, so there is no SDK profile or graphics-backend
selection:

```bash
./build-sdk.sh
```

On Windows:

```powershell
.\build-sdk.ps1
```

The result is written to `sdk/` and contains installed CMake packages, headers,
libraries, the isolated `bin/termin_python` launcher, Core wheels, provenance
manifests and the canonical CPython 3.14t runtime. The first build may download
the exact toolchain inputs recorded under `build-system/`.

Native-only platform SDKs are separate products. They contain static Core
libraries, headers and installed CMake packages, but no host Python runtime or
wheels:

```bash
./build-sdk-android.sh --ndk /absolute/path/to/android-ndk
./build-sdk-web.sh --setup
```

Android output is written to `sdk-platform/android/<abi>/`, Web output to
`sdk-platform/web/wasm32/`. Each tree has a `termin-core-platform.json` that
binds its system, architecture, API/toolchain version, owned artifact hashes
and `native_build_id`. Consumers must pin both the SDK tree and that identity;
a host, Android or Web Core SDK is never substituted for another platform.

Verify installed external consumption and relocation with:

```bash
./sdk/bin/termin_python -I scripts/smoke-installed-core-consumers --sdk-root sdk
./sdk/bin/termin_python -m termin_build.relocated_sdk_smoke --sdk-root sdk
```

Run the repository tests through `./run-tests.sh` after initializing the one
test-only submodule:

```bash
git submodule update --init termin-thirdparty/guard
./run-tests.sh
```

See [the repository boundary](docs/architecture/2026-08-13-core-domain-repositories.md)
and [the extraction plan](docs/plans/2026-08-13-termin-core-repository-extraction.md).
