# termin-inspect

Библиотека inspect/kind подсистемы для движка **Termin**.

Реализует runtime-рефлексию и сериализацию полей объектов через language-aware dispatch.
Поддерживает C, C++ и Python объекты через единый API.

## Возможности

- **Inspect dispatcher** — get/set/serialize/deserialize полей по `type_name` и `path`.
- **Kind system** — language-aware сериализация типов (`bool`, `int`, `vec3`, `quat`, пользовательские).
- **Наследование типов** — parent является частью атомарно публикуемого runtime type descriptor.
- **C++ runtime** — read-only `InspectRegistry`, `InspectFacetBuilder`, `KindRegistryCpp` и descriptor-only макросы полей.
- **Python bridge** — staged inspect facet Python-класса, публикуемый вместе с runtime type descriptor.

## Сборка

```bash
cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DTI_BUILD_TESTS=ON \
  -DTERMIN_BUILD_PYTHON=ON \
  -DCMAKE_PREFIX_PATH=/path/to/termin-base/install

cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

Без Python bridge:

```bash
cmake -S . -B build -DTERMIN_BUILD_PYTHON=OFF ...
```

## Документация

Документация собирается через MkDocs (GitHub Pages).

- Исходники: [`docs/`](docs/)
- Конфигурация: [`mkdocs.yml`](mkdocs.yml)

Локальный просмотр:

```bash
pip install mkdocs mkdocs-material
mkdocs serve
```

## Структура

```
include/
  inspect/         # Публичные заголовки: tc_inspect.h, tc_kind.h, *_python.hpp, *_cpp.hpp
  tc_inspect_cpp.hpp  # C++ InspectRegistry API
src/               # Реализация (C dispatcher, C++ runtime)
python/            # Python bridge (nanobind)
docs/              # Документация (MkDocs)
tests/             # Тесты
```
