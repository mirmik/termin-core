# API Reference

## Публичные заголовки

| Заголовок | Описание |
|-----------|----------|
| `include/inspect/tc_inspect.h` | C dispatcher: get/set/serialize/field info |
| `include/inspect/tc_kind.h` | C dispatcher: kind serialize/deserialize |
| `include/tc_inspect_cpp.hpp` | C++ InspectRegistry, макросы регистрации |
| `include/inspect/tc_kind_cpp.hpp` | C++ KindRegistryCpp |
| `include/inspect/tc_inspect_python.hpp` | Python inspect bridge (при `TERMIN_BUILD_PYTHON=ON`) |
| `include/inspect/tc_kind_python.hpp` | Python kind bridge (при `TERMIN_BUILD_PYTHON=ON`) |

## Точки инициализации

| Функция | Слой | Описание |
|---------|------|----------|
| `tc_inspect_kind_core_init()` | C | Инициализация dispatcher |
| `tc::init_cpp_inspect_vtable()` | C++ | Регистрация C++ language backend |
| `tc::init_python_lang_vtable()` | Python | Регистрация Python language backend |

Порядок вызова: core -> C++ -> Python. См. [Интеграция](integration.md).

## Совместимость

Сохранены обратно совместимые символы для существующих consumers:

| Символ | Статус | Замена |
|--------|--------|--------|
| `tc_inspect_python_adapter_init()` | deprecated | `tc::init_python_lang_vtable()` |
| `tc_init_full()` | deprecated | Явная последовательность init |

## Как читать API

Для каждой функции проверяйте:

- **Preconditions** — какие init должны быть вызваны, какие type_name зарегистрированы.
- **Ownership** — кто владеет возвращённым `tc_value*` (обычно caller).
- **Fail-soft** — что возвращается при невалидных входах.
