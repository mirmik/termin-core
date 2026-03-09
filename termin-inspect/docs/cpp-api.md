# C++ API

## InspectRegistry

Singleton-реестр полей для C++ типов. Обеспечивает get/set, наследование и сериализацию.

### Регистрация полей

```cpp
auto& reg = tc::InspectRegistry::instance();

// Простое поле — указатель на member
reg.add<Player, int>("Player", &Player::hp, "hp", "HP", "int");
reg.add<Player, std::string>("Player", &Player::name, "name", "Name", "string");
```

### Наследование

```cpp
struct Base { int hp = 100; };
struct Derived : Base { std::string name = "unit"; };

reg.add<Base, int>("Base", &Base::hp, "hp", "HP", "int");
reg.add<Derived, std::string>("Derived", &Derived::name, "name", "Name", "string");
reg.set_type_parent("Derived", "Base");

// all_fields("Derived") вернёт поля Derived + Base
```

### Get / Set

```cpp
tc_value* val = reg.get(&obj, "Player", "hp");
reg.set(&obj, "Player", "hp", new_value, context);
```

### Serialize / Deserialize

```cpp
tc_value* data = reg.serialize(&obj, "Player");
reg.deserialize(&obj, "Player", data, context);
```

## KindRegistryCpp

Реестр C++ kind handlers для конвертации `std::any <-> tc_value`.

```cpp
auto& kinds = tc::KindRegistryCpp::instance();

// Регистрация пользовательского kind
kinds.register_kind("my_color",
    [](const std::any& val) -> tc_value* {
        auto& c = std::any_cast<const MyColor&>(val);
        // ... serialize to tc_value
    },
    [](tc_value* val, void* ctx) -> std::any {
        // ... deserialize from tc_value
        return MyColor{...};
    }
);

// Использование
tc_value* v = kinds.serialize("my_color", color_any);
std::any restored = kinds.deserialize("my_color", v, ctx);

// Список зарегистрированных kinds
auto list = kinds.kinds();
```

## Макросы регистрации

В `tc_inspect_cpp.hpp` доступны helper-макросы для типичных паттернов:

| Макрос | Описание |
|--------|----------|
| `INSPECT_FIELD` | Простое поле (member pointer) |
| `INSPECT_FIELD_RANGE` | Числовое поле с min/max |
| `INSPECT_FIELD_CALLBACK` | Поле с callback при изменении |
| `INSPECT_FIELD_CHOICES` | Поле с фиксированным набором значений |
| `INSPECT_BUTTON` | Action-кнопка (без данных, только callback) |
| `SERIALIZABLE_FIELD` | Поле, участвующее в serialize/deserialize |
