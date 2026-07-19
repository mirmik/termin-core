# termin-build-tools

`termin-build-tools` contains Python build helpers shared by Termin packages.

Связанные документы:

- [Build system](../../docs/build-system.md)

## Основные области

- Python package `termin_build`.
- `termin_build.cmake_ext` with setuptools/CMake build classes used by native Python packages.
- SDK orchestration, including isolated Python wheel preparation, offline
  runtime population, runtime manifest generation and verification.
- Strict schema-v2 artifact manifests: relocatable SDK entries are resolved
  relative to the manifest, while developer build artifacts require an
  explicitly selected build manifest.

## Публичный API

Build scripts use:

```python
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
```

This package is build-time infrastructure, not runtime engine API.
