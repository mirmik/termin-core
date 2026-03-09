# Pre-Migration Cleanup Checklist (`termin` -> `termin-inspect`)

Дата среза: **March 4, 2026**.

Цель: вычистить текущие смешанные зависимости до фактического переноса кода в `termin-inspect`.

## 1. API boundary cleanup (C layer)

- [x] Разделить `tc_inspect.h` на core API и adapter API.
- [x] В core-хедере оставить только generic:
  - `tc_inspect_*`
  - `tc_kind_*`
  - `tc_kind_parse`
- [x] Убрать из core-хедера:
  - `tc_component_inspect_*`
  - `tc_pass_inspect_*`
  - `tc_component_set_field_*`/`tc_component_get_field_*`
  - включения `tc_mesh.h`/`tc_material.h`
- [x] Вынести component/pass/FFI функции в adapter headers (scene/render level).

Критерий:
- core header не содержит зависимостей на `tc_component`, `tc_pass`, `tc_mesh`, `tc_material`.

## 2. C++ inspect action abstraction

- [x] Убрать component-centric тип action callback:
  - заменить `std::function<void(tc_component*)>` на generic callback.
- [x] Ввести `InspectContext` (scene handle + user context).
- [x] Обновить `InspectFieldInfo::action` и вызовы `action_field(...)`.
- [x] Переписать `INSPECT_BUTTON` macro на generic вариант (без обязательного `CxxComponent::from_tc` в core).

Критерий:
- в core C++ inspect runtime нет прямой зависимости action-механизма от `tc_component`.

## 3. Split mixed runtime file (`tc_inspect_instance.cpp`)

- [x] Разделить текущий mixed файл на:
  - core vtable wiring / registry bootstrap
  - scene component adapter
  - render pass adapter
- [x] Из core части убрать include-ы на render (`frame_pass`) и domain resources.

Критерий:
- core inspect C++ файл не включает `render/tc_pass.h`, `frame_pass.hpp`, mesh/material registry API.

## 4. KindRegistryCpp domain cleanup

- [x] Убрать auto-registration `tc_mesh`/`tc_material` из `KindRegistryCpp::instance()`.
- [x] Оставить в core только builtin kinds (bool/int/float/double/string/vec3/quat + универсальные list-паттерны, если есть).
- [x] Перенести регистрацию domain kinds в consumer adapters (scene/render layer).

Критерий:
- `tc_kind_cpp` в core не включает `termin/mesh/*` и `termin/material/*`.

## 5. Python inspect/kind abstraction cleanup

- [x] Отделить generic Python bridge от scene-specific mapping.
- [x] Убрать из core Python inspect bridge прямой доступ к `tc_component`/`tc->body`.
- [x] Ввести adapter callback/object resolver для:
  - object unwrap
  - action invocation target
- [x] Оставить nanobind module wiring, завязанный на `termin._native`, в consumer слое.

Критерий:
- Python core bridge работает с абстрактным `void*`/`PyObject*` без include/use `core/tc_component.h`.

## 6. Initialization decoupling

- [x] Убрать склейку “всё сразу” через `tc_init_full()`.
- [x] Разделить init-функции по слоям:
  - inspect/kind core init
  - scene adapter init
  - render adapter init
  - python adapter init
- [x] Явно определить порядок вызова init в `termin` startup.

Критерий:
- core init не вызывает регистрацию scene/render domain kinds автоматически.

## 7. Adapter compatibility window

- [x] Сохранить текущие внешние API как thin wrappers:
  - `tc_component_inspect_*`
  - `tc_pass_inspect_*`
  - C#/Python FFI входы
- [x] Перевести реализации wrappers на новый generic core API.
- [x] Зафиксировать deprecation notes (без fallback-слоёв в core).

Критерий:
- существующие callsites в `termin`/C#/Python работают без массовой одномоментной переписи.

## 8. Singleton/link topology guardrails

- [x] Определить единый binary owner для `InspectRegistry` и `KindRegistryCpp`.
- [x] Проверить, что при линковке `termin-inspect` + adapters не возникает дублей singleton.
- [x] Добавить smoke-проверку на shared-lib topology.

Критерий:
- runtime видит единые registry instance во всех потребителях.

## 9. Test baseline before extraction

- [ ] C tests:
  - [x] `tc_kind_parse`
  - [x] inspect/kind dispatcher with mock lang registries
- [ ] C++ tests:
  - [x] `InspectRegistry` add/get/set
  - [x] inheritance field traversal
  - [x] generic action callback invocation
- [ ] Python tests:
  - register fields + get/set/serialize/deserialize для generic объектов
  - lazy list handler
- [ ] Integration tests:
  - component adapter path
  - pass adapter path
  - external domain kind registration path (`tc_mesh`, `tc_material`)

Критерий:
- тесты зелёные до начала фактического переноса файлов.

## 10. Execution gate (go/no-go)

- [x] Все пункты 1-6 закрыты.
- [x] Есть совместимость через adapter wrappers (пункт 7).
- [x] Зафиксирован владелец singleton (пункт 8).
- [ ] Есть зелёный тестовый baseline (пункт 9).

После этого можно начинать перенос кода в `termin-inspect` по этапам `inspect_kind_extraction_plan.md`.
