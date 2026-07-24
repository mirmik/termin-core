# termin-build-tools

`termin-build-tools` contains Python build helpers shared by Termin packages.

Связанные документы:

- [Build system](../../docs/build-system.md)

## Основные области

- Python package `termin_build`.
- `termin_build.cmake_ext` with setuptools/CMake build classes used by native Python packages.
- SDK orchestration, including isolated Python wheel preparation, offline
  runtime population, runtime manifest generation and verification.
- Exact-pinned CPython 3.14t acquisition: a SHA-verified Linux source build
  with `--disable-gil`, an official Windows free-threaded NuGet input, stable
  cache fingerprints, offline reuse and hard runtime identity probes. Host
  Python only bootstraps the orchestrator; it is never selected as the SDK
  target implicitly.
- Strict schema-v3 artifact manifests: relocatable SDK entries are resolved
  relative to the manifest, while developer build artifacts require an
  explicitly selected build manifest. Every manifest carries the canonical
  Python ABI identity: `version`, `soabi`, `free_threaded` and
  `py_gil_disabled`.
- One content-derived native build ID shared by installed runtime metadata and
  public wheels. The Python ABI identity participates in that ID, and final
  verification rejects runtime, application payload, overlay and native wheel
  ABI mismatches before importing an extension.

## Публичный API

Build scripts use:

```python
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
```

This package is build-time infrastructure, not runtime engine API.
