# Наследование типов

## Принцип

Каждый тип хранит только **собственные** поля. Родительские поля не дублируются — при запросе система рекурсивно обходит цепочку предков.

```
Component          [hp, speed]
    └── MeshRenderer   [mesh, material]

all_fields("MeshRenderer") → [hp, speed, mesh, material]
fields("MeshRenderer")     → [mesh, material]
```

## Хранение

`InspectRegistry` содержит два словаря:

| Словарь | Ключ | Значение |
|---------|------|----------|
| `_fields` | `type_name` | Только собственные поля типа |
| `_type_parents` | `type_name` | Имя родительского типа (строка) |

## Регистрация родителя

### C++

Макро `REGISTER_COMPONENT` автоматически регистрирует родителя:

```cpp
// component_registry.hpp
REGISTER_COMPONENT(MeshRenderer, Component);

// Внутри раскрывается в:
InspectRegistry::instance().set_type_parent("MeshRenderer", "Component");
```

Ручная регистрация:

```cpp
auto& reg = InspectRegistry::instance();
reg.add<Base, int>("Base", &Base::hp, "hp", "HP", "int");
reg.add<Derived, std::string>("Derived", &Derived::title, "title", "Title", "string");
reg.set_type_parent("Derived", "Base");
```

### Python

`__init_subclass__` обходит MRO и находит ближайшего предка с `inspect_fields`:

```python
class Enemy(PythonComponent):
    inspect_fields = {"hp": ("int", "HP")}

class Boss(Enemy):
    inspect_fields = {"phase": ("int", "Phase")}
```

При определении `Boss` система:

1. Обходит `Boss.__mro__` → находит `Enemy` как ближайший предок с `inspect_fields`
2. Вызывает `registry.set_type_parent("Boss", "Enemy")`
3. Регистрирует только собственные поля `Boss` (без `hp`)

## Разрешение полей

Все методы запроса полей работают рекурсивно:

### `all_fields(type_name)`

Собирает полный список: сначала поля родителя (рекурсивно), потом собственные.

```cpp
std::vector<InspectFieldInfo> all_fields(const std::string& type_name) const {
    std::vector<InspectFieldInfo> result;
    std::string parent = get_type_parent(type_name);
    if (!parent.empty()) {
        auto parent_fields = all_fields(parent);
        result.insert(result.end(), parent_fields.begin(), parent_fields.end());
    }
    auto it = _fields.find(type_name);
    if (it != _fields.end()) {
        result.insert(result.end(), it->second.begin(), it->second.end());
    }
    return result;
}
```

Порядок полей: **родительские первыми**, затем собственные (как в C++ memory layout).

### `find_field(type_name, path)`

Сначала ищет в собственных полях, потом рекурсивно в родителе:

```cpp
const InspectFieldInfo* find_field(const std::string& type_name,
                                    const std::string& path) const {
    // Сначала свои
    auto it = _fields.find(type_name);
    if (it != _fields.end()) {
        for (const auto& f : it->second) {
            if (f.path == path) return &f;
        }
    }
    // Потом родитель
    std::string parent = get_type_parent(type_name);
    if (!parent.empty()) {
        return find_field(parent, path);
    }
    return nullptr;
}
```

### `get_field_by_index(type_name, index)`

Учитывает смещение: если индекс попадает в диапазон родителя — делегирует туда, иначе вычитает `parent_count` и ищет в собственных.

## C API

Диспетчер предоставляет единую функцию:

```c
const char* tc_inspect_get_base_type(const char* type_name);
```

Возвращает имя родителя или `NULL`. Внутри вызывает `get_parent` из языкового vtable.

Важно: `tc_inspect_field_count()` и `tc_inspect_get_field()` уже возвращают данные **с учётом наследования** — C++ vtable делегирует в `all_fields_count()` и `get_field_by_index()`.

## Сериализация

`all_fields()` используется при сериализации/десериализации — все унаследованные поля обрабатываются автоматически:

```cpp
// tc_inspect_python.cpp — десериализация с наследованием
for (const auto& f : reg.all_fields(type_name)) {
    if (!f.is_serializable) continue;
    if (!f.setter) continue;
    // ... восстановление поля из данных
}
```

## Полный пример

```cpp
struct CppBaseComponent {
    int hp = 100;
    float speed = 2.5f;
};

struct CppDerivedComponent : public CppBaseComponent {
    std::string title = "rookie";
};

auto& reg = InspectRegistry::instance();

// Регистрация полей — каждый тип только свои
reg.add<CppBaseComponent, int>(
    "CppBaseComponent", &CppBaseComponent::hp, "hp", "HP", "int");
reg.add<CppBaseComponent, float>(
    "CppBaseComponent", &CppBaseComponent::speed, "speed", "Speed", "float");
reg.add<CppDerivedComponent, std::string>(
    "CppDerivedComponent", &CppDerivedComponent::title, "title", "Title", "string");

// Связь наследования
reg.set_type_parent("CppDerivedComponent", "CppBaseComponent");

// Результат
reg.all_fields_count("CppDerivedComponent");        // 3 (hp, speed, title)
reg.find_field("CppDerivedComponent", "hp");         // найдено — от родителя
reg.find_field("CppDerivedComponent", "title");      // найдено — собственное
reg.fields("CppDerivedComponent").size();             // 1 (только title)
```
