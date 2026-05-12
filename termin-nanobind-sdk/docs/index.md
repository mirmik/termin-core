# termin-nanobind-sdk / termin-nanobind

`termin-nanobind-sdk` ships nanobind runtime helpers used by Termin Python packages.

Связанные документы:

- [README](../README.md)
- [Build system](../../docs/build-system.md)

## Основные области

- Python package `termin_nanobind`.
- Runtime SDK discovery and shared-library preload helpers in `python/termin_nanobind/`.
- CMake package files for nanobind integration.

## Публичный API

Python package:

```python
from termin_nanobind.runtime import preload_sdk_libs
```

Most Termin packages call `preload_sdk_libs(...)` from their `__init__.py` to load SDK shared libraries before importing nanobind extensions.

