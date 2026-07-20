# Python bridge

Python bridge построен на nanobind и добавляет inspect/kind поддержку для Python-классов.
Включается опцией `TERMIN_BUILD_PYTHON=ON` при сборке.

## Архитектура

```
Python class  ──→  InspectRegistryPythonExt  ──→  C dispatcher
                   KindRegistryPython        ──→  tc_kind dispatch
```

Python bridge регистрирует себя как language backend в C dispatcher.
После этого `tc_inspect_get/set/serialize/deserialize` работают для Python-объектов так же, как для C++.

## Основные сущности

### InspectRegistryPythonExt

Bridge извлекает декларативные `inspect_fields` Python-класса в отдельный
`InspectFacetBuilder`. Публичного `InspectRegistry.register_python_fields()`
нет: component publisher присоединяет staged facet к component runtime
descriptor и публикует их одной транзакцией.

Операции:

- `build_python_inspect_facet(type_name, fields)` — построение staged facet в C++ publisher.
- `get(obj, type_name, path)` — чтение поля через `getattr`.
- `set(obj, type_name, path, value, context)` — запись через `setattr`.
- `deserialize_all_py(obj, type_name, data, context)` — десериализация всех полей из `tc_value`.

Ошибка при чтении или валидации любого поля возникает до commit и не создаёт
type shell. Python-код объявляет класс и metadata, но сам импорт не меняет live
registry; builtin bootstrap или module transaction выполняет публикацию.

### KindRegistryPython

Регистрация Python handlers для пользовательских kinds:

```python
register_python_kind("my_type",
    serialize=lambda val: to_tc_value(val),
    deserialize=lambda tv, ctx: from_tc_value(tv),
)
```

### KindRegistry (facade)

Объединяет C++ и Python kind реестры. При вызове `serialize_any` / `deserialize_any` пробует оба backend.

## Наследование Python типов

Работает так же, как в C++:

1. Построить и committed descriptor родителя.
2. Построить descriptor потомка с именем родителя и только собственными полями.

После этого `all_fields("ChildComponent")` включает поля родителя.

## Ограничения

- Python runtime должен быть инициализирован до вызова `init_python_lang_vtable()`.
- Nanobind и Python dev headers должны быть доступны при сборке.
- Python module wiring remains in consumer/domain packages, not in
  `termin-inspect` core.
