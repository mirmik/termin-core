# Архитектура

## Общая схема

```
┌─────────────────────────────────────────────┐
│              Consumer (termin)               │
│   component adapters, pass adapters, UI     │
├─────────────────────────────────────────────┤
│           Python bridge (nanobind)          │
│  InspectRegistryPythonExt, KindRegistryPy   │
├─────────────────────────────────────────────┤
│              C++ runtime                    │
│     InspectRegistry, KindRegistryCpp        │
├─────────────────────────────────────────────┤
│            C dispatcher                     │
│    tc_inspect_*, tc_kind_* (language vtable) │
├─────────────────────────────────────────────┤
│            termin_base                      │
│         tc_value, tc_log, types             │
└─────────────────────────────────────────────┘
```

## Слои

### 1. C dispatcher (`src/tc_inspect.c`, `src/tc_kind.c`)

Нижний слой. Определяет единый C API surface и маршрутизирует вызовы через language vtable.
Не знает ни про C++, ни про Python — только про зарегистрированные vtable-записи.

### 2. C++ runtime (`tc_inspect_cpp.hpp`, `tc_kind_cpp.hpp`)

- `InspectRegistry` — singleton для регистрации полей, наследования, get/set/serialize/deserialize.
- `KindRegistryCpp` — сериализация C++ типов (`std::any <-> tc_value`), builtin kinds.

Регистрирует себя как language backend в C dispatcher.

### 3. Python bridge (`tc_inspect_python.hpp`, `tc_kind_python.hpp`)

- `InspectRegistryPythonExt` — регистрация полей Python-классов, Python get/set.
- `KindRegistryPython` — Python handlers для serialize/deserialize.
- `KindRegistry` — facade, объединяющий C++ и Python registry.

Регистрирует себя как отдельный language backend в C dispatcher.

## Инициализация

Порядок вызовов при запуске:

1. `tc_inspect_kind_core_init()` — инициализация C dispatcher.
2. `tc::init_cpp_inspect_vtable()` — регистрация C++ language backend.
3. `tc::init_python_lang_vtable()` — регистрация Python language backend (если включён).

Consumer-слой затем регистрирует свои adapter init (component adapters, domain kinds и т.д.).

## Принцип контекста

Inspect/Kind не завязаны на `tc_scene_handle` внутри API.
Контекст передаётся как `void*` и интерпретируется consumer-слоем.

Это позволяет использовать inspect/kind для любых объектов — не только компонентов сцены.
