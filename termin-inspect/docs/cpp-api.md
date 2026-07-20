# C++ API

## InspectFacetBuilder и InspectRegistry

`InspectFacetBuilder` собирает полное описание inspect facet вне live registry.
`InspectRegistry` после commit предоставляет только query/get/set и сериализацию.

```cpp
tc::InspectFacetBuilder inspect("Player");
inspect.add<Player, int>(
    "Player", &Player::hp, "hp", "HP", "int");
inspect.add<Player, std::string>(
    "Player", &Player::name, "name", "Name", "string");

auto* descriptor = tc_runtime_type_descriptor_create(
    "Player", "gameplay", "BaseActor");
if (!inspect.attach_to(descriptor) ||
    !tc_runtime_type_registry_commit_descriptor(descriptor)) {
    throw std::runtime_error("Player descriptor commit failed");
}
```

В component/pass коде raw descriptor не нужен: `ComponentTypeDescriptorBuilder`
и `FramePassTypeDescriptorBuilder` уже содержат `inspect()` и публикуют factory,
parent, metadata и inspect facet одним commit. Родитель публикуется раньше
потомка. После commit дописывать поля, parent или metadata нельзя.

### Query / Get / Set

```cpp
auto& reg = tc::InspectRegistry::instance();
auto fields = reg.all_fields("Player");
tc_value value = reg.get_tc_value(&player, "Player", "hp");
reg.set_tc_value(&player, "Player", "hp", new_value, context);
```

### Serialize / Deserialize

```cpp
tc_value data = reg.serialize_all(&player, "Player");
reg.deserialize_all(&player, "Player", &data, context);
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

Макросы создают только overload, принимающий `InspectFacetBuilder&`. Тип вызывает
его при сборке своего component/pass descriptor; no-argument overloads,
inline-static registrars и `TC_MODULE_INSPECT_*` удалены. Повторный commit не
считается идемпотентным успехом: replacement должен быть явно разрешён и иметь
того же owner.
