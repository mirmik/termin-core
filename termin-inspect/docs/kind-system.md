# Kind System

`tc_kind` — language-aware dispatcher для сериализации и десериализации типов.

Kind — это именованный тип данных (`"int"`, `"vec3"`, `"list[string]"`), для которого зарегистрированы handlers конвертации `native value <-> tc_value`.

## Языковые реестры

Для каждого языка (`C++`, `Python`, ...) регистрируется `tc_kind_lang_registry` с операциями:

| Операция | Описание |
|----------|----------|
| `has(kind)` | Проверка наличия handler для kind |
| `serialize(kind, input)` | Native value -> `tc_value` |
| `deserialize(kind, input, context)` | `tc_value` -> native value |
| `list(...)` | Список зарегистрированных kinds |

## C API

### Проверка

```c
bool exists = tc_kind_exists("vec3");
bool has_cpp = tc_kind_has_lang("vec3", "cpp");
```

### Сериализация с указанием языка

```c
tc_value* val = tc_kind_serialize("vec3", "cpp", native_input);
void* obj = tc_kind_deserialize("vec3", "cpp", val, context);
```

### Автоматический выбор языка

```c
tc_value* val = tc_kind_serialize_any("vec3", native_input);
void* obj = tc_kind_deserialize_any("vec3", val, context);
```

`*_any` варианты пробуют зарегистрированные языки по приоритету.

## C++ runtime (KindRegistryCpp)

`KindRegistryCpp` хранит C++ handlers (`std::any <-> tc_value`).

Builtin kinds из коробки:

| Kind | C++ тип |
|------|---------|
| `bool` | `bool` |
| `int` | `int` |
| `float` | `float` |
| `double` | `double` |
| `string` | `std::string` |
| `vec3` | `tc_vec3` |
| `quat` | `tc_quat` |
| `enum` | enum через string mapping |

Пользовательские kinds регистрируются через `register_kind(name, serialize_fn, deserialize_fn)`.

## Составные kinds

Поддерживается синтаксис `list[T]` — список элементов типа `T`.
Parser разбирает строку kind и создаёт handler автоматически, если handler для `T` уже зарегистрирован.
