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

Регистрация полей Python-классов:

```python
# На стороне Python (через nanobind-биндинги)
register_python_fields("MyComponent", [
    {"name": "speed", "display_name": "Speed", "kind": "float"},
    {"name": "target", "display_name": "Target", "kind": "string"},
])
```

Операции:

- `register_python_fields(type_name, fields)` — регистрация полей.
- `get(obj, type_name, path)` — чтение поля через `getattr`.
- `set(obj, type_name, path, value, context)` — запись через `setattr`.
- `deserialize_all_py(obj, type_name, data, context)` — десериализация всех полей из `tc_value`.

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

1. Зарегистрировать поля каждого типа.
2. Указать наследование: `set_type_parent("ChildComponent", "BaseComponent")`.

После этого `all_fields("ChildComponent")` включает поля родителя.

## Ограничения

- Python runtime должен быть инициализирован до вызова `init_python_lang_vtable()`.
- Nanobind и Python dev headers должны быть доступны при сборке.
- Биндинги `termin._native` (module wiring) остаются в consumer-слое, не в core.
