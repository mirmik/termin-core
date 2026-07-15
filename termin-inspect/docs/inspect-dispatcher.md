# Inspect Dispatcher

`tc_inspect` — dispatcher, который маршрутизирует вызовы рефлексии через language vtable.
Вызывающий код работает с единым C API, а конкретная реализация (C++, Python) подключается как backend.

## Базовые операции

### Проверка типа

```c
bool exists = tc_inspect_has_type("Player");
```

### Чтение поля

```c
tc_value* val = tc_inspect_get(obj, "Player", "hp");
```

### Запись поля

```c
tc_inspect_set(obj, "Player", "hp", new_value, context);
```

Для migration/restore-кода доступен проверяемый вариант:

```c
bool accepted = tc_inspect_set_checked(obj, "Player", "hp", new_value, context);
```

`accepted == true` означает, что поле найдено, доступно для записи, kind
conversion завершилась и setter действительно применил значение. Ошибка
конвертации, исключение setter-а, неизвестное или read-only поле возвращают
`false` и логируются. Само значение `TC_VALUE_NIL` не является признаком
ошибки: nullable-поле может успешно принять его; результат операции передаётся
только отдельным `bool`.

`tc_inspect_deserialize_checked` также передаёт `TC_VALUE_NIL` в checked
setter, не прогоняя его через старый kind API, где `nil` исторически служит
sentinel-ом ошибки. Поэтому nullable setter применит значение, а non-nullable
setter вернёт обычную проверяемую ошибку.

C++-регистрации полей используют тот же контракт через
`InspectFieldInfo::setter` и `InspectRegistry::set_tc_value`. Ручной setter
обязан вернуть `true` только после применения значения. Python backend
преобразует исключение kind handler-а или setter-а в `false`, не пропуская его
через C ABI.

### Сериализация / десериализация

```c
tc_value* data = tc_inspect_serialize(obj, "Player");
tc_inspect_deserialize(obj, "Player", data, context);
```

`tc_inspect_deserialize` предназначен для обычного best-effort применения.
Lossless restore должен использовать `tc_inspect_deserialize_checked`: он
останавливается на первом неизвестном/non-serializable поле, ошибке kind
conversion или setter и возвращает `tc_inspect_apply_result` с `status`,
`applied_fields` и `field_path`. Функция не откатывает уже применённые поля;
поэтому atomic migration выполняется на ещё не опубликованном candidate object.

## Поля и метаданные

Информация о полях доступна без доступа к самому объекту:

```c
int count = tc_inspect_field_count("Player");

tc_inspect_field_info info;
tc_inspect_get_field_info("Player", 0, &info);  // по индексу
tc_inspect_find_field_info("Player", "hp", &info);  // по path
```

`tc_inspect_field_info` содержит: `name`, `display_name`, `kind`, `path` и метаданные (range, choices и др.).

## Поведение на ошибках

Обычные interactive-вызовы используют модель fail-soft:

- Невалидный `type_name` или `path` — возвращает `nil` / `false`, выполняет no-op.
- Ошибки логируются через `tc_log` (уровень WARN/ERROR).
- Dispatcher не бросает исключений и не аварийно завершается.

Checked-вызовы также не пропускают исключения backend-а через C ABI, но
возвращают `false`/fallible status. Неизвестные поля в checked payload считаются
schema drift; вызывающий migration layer обязан сохранить исходный payload или
явно преобразовать его до применения.
