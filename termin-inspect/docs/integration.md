# Интеграция

## Через CMake

```cmake
find_package(termin_inspect REQUIRED)
target_link_libraries(my_target PRIVATE termin_inspect::termin_inspect)
```

Если `termin_inspect` установлен в нестандартный путь:

```bash
cmake -S . -B build -DCMAKE_PREFIX_PATH=/opt/termin
```

## Порядок инициализации

Инициализация разделена по слоям. Порядок вызовов при запуске:

```cpp
// 1. Core inspect/kind dispatcher
tc_inspect_kind_core_init();

// 2. C++ language backend
tc::init_cpp_inspect_vtable();

// 3. Python language backend (опционально)
tc::init_python_lang_vtable();

// 4. Consumer adapters (в termin)
my_component_adapter_init();   // регистрация component inspect
my_render_adapter_init();      // регистрация pass inspect
my_domain_kinds_init();        // регистрация domain kinds (tc_mesh, tc_material, ...)
```

Каждый шаг зависит от предыдущего. Не меняйте порядок.

## Внутри termin

Ожидаемая схема интеграции:

1. `termin-core` и `entity_lib` линкуются с `termin_inspect::termin_inspect`.
2. Inspect adapters (component/pass) остаются в consumer-слое.
3. Domain kinds (`tc_mesh`, `tc_material`) регистрируются в consumer, не в core.
4. Consumer вызывает core init и свои adapter init в нужном порядке.

## Runtime

Убедитесь, что `libtermin_inspect.so` доступна в runtime path:

- `LD_LIBRARY_PATH` — для разработки.
- Install rpath — для установки.
- Копирование в дистрибутив — для standalone.

## Совместимость

Для существующих consumers сохранены обратно совместимые символы:

- `tc_inspect_python_adapter_init()` — thin wrapper над новым init.
- `tc_init_full()` — вызывает все init в правильном порядке.

Эти символы deprecated и будут удалены в будущих версиях.
