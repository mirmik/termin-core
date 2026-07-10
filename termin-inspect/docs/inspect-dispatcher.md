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
