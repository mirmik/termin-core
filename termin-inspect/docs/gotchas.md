# Ограничения и gotchas

## Имена типов

Dispatch не «угадывает» типы: `type_name` должен **точно** совпадать с именем, переданным при регистрации.
Нет fuzzy matching, нет namespace resolution — только строковое равенство.

## Наследование

`set_type_parent` задаёт inheritance только на уровне registry metadata.
Это **не** C++ inheritance — registry не знает про vtable и dynamic_cast.
Наследование влияет только на `all_fields()` и порядок serialize/deserialize.

## Контекст десериализации

В `deserialize` context — это `void*`. Интерпретация полностью лежит на consumer-слое.
Core ничего не знает о содержимом контекста: это может быть `tc_scene_handle`, указатель на editor, или `NULL`.

## Singleton топология

`InspectRegistry` и `KindRegistryCpp` — singleton-и. При неправильной link-топологии (например, статическая линковка в нескольких `.so`) могут возникнуть дубли.
Убедитесь, что `libtermin_inspect.so` линкуется единообразно во всех потребителях.

## Python bridge

- Python runtime должен быть инициализирован **до** `init_python_lang_vtable()`.
- При сборке с `TERMIN_BUILD_PYTHON=ON` в системе должны быть nanobind и Python dev headers.
- GIL должен быть захвачен при вызовах Python inspect из C++ потоков.

## Fail-soft поведение

Все публичные функции dispatcher работают в fail-soft режиме: на невалидных входах возвращают `nil`/`false`/no-op.
Если нужен fail-fast для отладки, добавляйте assert-ы на уровне вызывающего кода.

## Порядок инициализации

Core init (`tc_inspect_kind_core_init`) должен быть вызван **до** регистрации language backends.
Language backends — **до** регистрации domain kinds и adapters.
Нарушение порядка приводит к silent no-op при dispatch.
