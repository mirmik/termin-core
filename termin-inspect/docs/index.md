# termin-inspect

`termin-inspect` — библиотека runtime-рефлексии и сериализации для движка Termin.

Пакет объединяет:

- **C dispatcher** — единый API для inspect (`tc_inspect_*`) и kind (`tc_kind_*`).
- **C++ runtime** — `InspectRegistry` (поля, наследование, get/set) и `KindRegistryCpp` (сериализация типов).
- **Python bridge** — nanobind-слой для Python-классов и kind handlers.

## Рекомендуемый маршрут

| #  | Раздел | Описание |
|----|--------|----------|
| 1  | [Быстрый старт](getting-started.md) | Сборка и проверка |
| 2  | [Архитектура](architecture.md) | Слои: C, C++, Python |
| 3  | [Inspect Dispatcher](inspect-dispatcher.md) | Get/set/serialize через language vtable |
| 4  | [Kind System](kind-system.md) | Языковые реестры типов |
| 5  | [C++ API](cpp-api.md) | InspectRegistry, KindRegistryCpp, макросы |
| 6  | [Наследование](inheritance.md) | Цепочки типов, разрешение полей |
| 7  | [Python bridge](python-bridge.md) | Регистрация Python-классов |
| 8  | [Интеграция](integration.md) | CMake, runtime, порядок инициализации |
| 9  | [API Reference](api.md) | Публичные заголовки и точки входа |
| 10 | [Ограничения и gotchas](gotchas.md) | Подводные камни |

## Scope

`termin-inspect` не зависит от `termin-scene`, `termin-graphics` или `termin-core`.

Зависимости:

- `termin_base` (типы, `tc_value`, логирование)
- опционально Python + nanobind (если включён `TERMIN_BUILD_PYTHON`)
