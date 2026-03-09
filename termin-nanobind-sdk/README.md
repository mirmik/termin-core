# termin-nanobind-sdk

Отдельный SDK-артефакт для `nanobind`, который устанавливает:

- `libnanobind.so`
- CMake package `nanobind`
- headers и исходники `nanobind`, которые нужны `nanobind_add_module(NB_SHARED)`

Идея простая: `nanobind` собирается один раз как общий SDK-компонент, а остальные пакеты `termin-*` больше не вызывают `nanobind_build_library(...)` локально.

## Локальная сборка

Нужен установленный Python package `nanobind`.

```bash
pip install nanobind
cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/opt/termin \
  -DPython_EXECUTABLE=$(which python3)
cmake --build build --parallel
sudo cmake --install build
```

После установки потребители могут использовать:

```cmake
find_package(Python COMPONENTS Interpreter Development REQUIRED)
find_package(nanobind CONFIG REQUIRED)
nanobind_add_module(my_module NB_SHARED ...)
```

## Артефакт SDK

CI публикует `sdk-nanobind.tar.gz` с layout под `/opt/termin`.
