# Build system

Termin Core is one SDK product. It has no product profiles or graphics backend
switches. The public repository command interface is
[Task](https://taskfile.dev/):

```console
task --list
task build
task test
task smoke
```

The same task names are used on Linux and Windows. `Taskfile.yml` selects a
shell launcher on POSIX systems and a PowerShell launcher on Windows.

## Command interface

| Task | Purpose |
| --- | --- |
| `task build` | Build and install the complete host SDK into `sdk/`. |
| `task test` | Build the SDK, run native and Python tests, then run installed and relocated SDK smokes. |
| `task smoke` | Run both SDK boundary smokes against an existing `sdk/`. |
| `task smoke:installed` | Verify an external consumer through installed SDK artifacts only. |
| `task smoke:relocated` | Copy and verify the SDK from a different location. |
| `task build:android -- <args>` | Build the native Android SDK on Linux. |
| `task build:web -- <args>` | Build the native Web SDK on Linux. |

Arguments following `--` are passed to the underlying platform launcher. For
example:

```console
task build:android -- --ndk /absolute/path/to/android-ndk
task build:web -- --setup
```

## Internal launchers

Task is the supported developer and CI entrypoint. Its implementation remains
available under `scripts/` for diagnostics and environments where Task cannot
be installed:

```text
scripts/build/       host, Android and Web SDK launchers
scripts/test/        complete and focused test launchers
```

Shell and PowerShell files with the same stem are platform equivalents. These
paths are internal and may change; automation should invoke Task instead.

The host launchers bootstrap the Python orchestrator in `termin-build-tools`.
The orchestrator prepares the pinned free-threaded CPython toolchain, invokes
the native and nanobind build stage, installs Python packages and wheels, and
verifies the resulting SDK manifests. The host Python found in `PATH` is only
used to bootstrap that pinned toolchain.

Useful environment overrides include:

- `BUILD_JOBS` for native build parallelism;
- `BUILD_DIR` for the host CMake build tree;
- `SDK_PREFIX` for the host SDK installation tree;
- `PYTHON_BIN` or `PYTHON_EXECUTABLE` for the bootstrap interpreter.

## Tests

The complete verification command is:

```console
git submodule update --init termin-thirdparty/guard
task test
```

It performs the following checks in order:

1. builds the complete installed SDK;
2. configures and runs the root native CTest graph;
3. prepares the checkout Python overlay using the SDK interpreter;
4. runs the Core Python suites and build-tool contract tests;
5. verifies installed external consumption;
6. verifies the SDK after relocation.

Python tests use `sdk/bin/termin_python` (or `termin_python.exe`) and the overlay
at `build/python-envs/test/overlay.json`. They must not fall back to a system
Python package environment or to sibling source checkouts.

## Platform SDKs

Android and Web are native-only SDK products. They contain static Core
libraries, headers, CMake package files and a platform identity manifest; they
do not contain the host Python runtime or wheels.

- Android installs into `sdk-platform/android/<abi>/`.
- Web installs into `sdk-platform/web/wasm32/`.

Each platform tree is verified after installation and cannot substitute for a
host SDK or for a platform SDK with a different identity.
