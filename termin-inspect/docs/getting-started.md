# Быстрый старт

## Зависимости

Перед сборкой установите `termin-base`:

```bash
cd ../termin-base
cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/termin
cmake --build build --parallel
cmake --install build
```

## Сборка

```bash
cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DTI_BUILD_TESTS=ON \
  -DTERMIN_BUILD_PYTHON=ON \
  -DCMAKE_PREFIX_PATH=/opt/termin

cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

Без Python bridge:

```bash
cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DTI_BUILD_TESTS=ON \
  -DTERMIN_BUILD_PYTHON=OFF \
  -DCMAKE_PREFIX_PATH=/opt/termin
```

## Опции CMake

| Опция | По умолчанию | Описание |
|-------|-------------|----------|
| `DTI_BUILD_TESTS` | `OFF` | Собирать тесты |
| `TERMIN_BUILD_PYTHON` | `OFF` | Собирать Python bridge (требует nanobind) |

## Что проверяют тесты

- **C dispatcher** — базовые контракты: регистрация типов, dispatch, fail-soft поведение.
- **C++ InspectRegistry** — add/get/set полей, наследование через `set_type_parent`.
- **Python integration** — регистрация Python-классов, serialize/deserialize с наследованием.

## Минимальный пример (C++)

```cpp
#include <tc_inspect_cpp.hpp>

struct Player {
    int hp = 100;
    std::string name = "hero";
};

// Регистрация полей
auto& reg = tc::InspectRegistry::instance();
reg.add<Player, int>("Player", &Player::hp, "hp", "HP", "int");
reg.add<Player, std::string>("Player", &Player::name, "name", "Name", "string");

// Использование
Player p;
tc_value* val = reg.get(&p, "Player", "hp");    // -> 100
reg.set(&p, "Player", "name", str_value, ctx);  // p.name = "hero" -> новое значение
```

## Что дальше

- [Архитектура](architecture.md) — как устроены слои dispatch.
- [C++ API](cpp-api.md) — полный API InspectRegistry и макросы регистрации.
