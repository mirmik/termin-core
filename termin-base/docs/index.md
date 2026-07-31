# termin-base / tcbase

`termin-base` содержит базовые типы и утилиты, на которые могут опираться остальные библиотеки Termin без зависимости от scene/render/gui/application слоев.

Python-пакет: `tcbase`.

## Process-wide resource loader

Ленивые native-ресурсы проходят через один нейтральный UUID callback из
`tcbase/tc_resource.h`. Host устанавливает его через
`tc_resource_set_loader()`, registries запрашивают загрузку через
`tc_resource_request_load()`, а shutdown снимает через
`tc_resource_clear_loader()`. Resource handles хранят только identity и loaded
state, но не callbacks или Python objects.

Жизненным циклом Python bridge владеет
`termin_assets.set_resource_manager_factory()`. На каждый запрос bridge получает
текущий canonical manager, находит canonical asset по UUID и вызывает
`Asset.ensure_loaded()`. Поэтому замена manager не удерживает старый экземпляр
в native interop state.

Связанные документы:

- [Module Map](../../docs/modules.md#termin-base--tcbase)
- [Build system](../../docs/build-system.md)
- [Canonical naming](../../docs/architecture/2026-03-15-canonical-naming.md)

## Основные области

- `tc_log` - общий C/C++ logging API. Помимо stderr и опционального platform
  callback, host может включить bounded capture queue через
  `tc_log_capture_start()`, забирать целостные `tc_log_record` вызовом
  `tc_log_capture_drain()` и завершить capture через
  `tc_log_capture_stop()`. Producer threads не вызывают consumer language/UI
  callbacks; при переполнении удаляются самые старые записи, а drain возвращает
  наблюдаемый `dropped_count`.
- `tc_pool` - единый handle/generation pool primitive. Обычный
  `tc_pool_init()` сохраняет неограниченный growable contract; владельцы с
  жёстким лимитом используют `tc_pool_init_ex()` с `max_capacity`, начальным
  generation и порядком выдачи индексов. Та же конфигурация принимает пару
  allocator/deallocator; тесты `tc_pool` используют её для детерминированного
  fault-injection. Инициализация и рост транзакционны: ошибка одной из
  storage-аллокаций не публикует частично заменённые массивы. Process-global
  registry с shutdown/rebootstrap хранит свой `tc_pool_generation_epoch` и
  передаёт его в `tc_pool_init_rebootstrap()` либо
  `tc_pool_config.generation_epoch`: `tc_pool_free()` продвигает epoch выше
  всех поколений прежнего pool, включая выросшие и переиспользованные slots.
  Переполнившийся slot выводится из обращения, а исчерпанный epoch запрещает
  rebootstrap fail-closed.
- `tc_resource_map` - generic resource map.
- `tc_tensor` - ABI-friendly typed strided memory descriptor для bulk buffers.
- `tc_value` - C tagged-union value type для сериализации и межмодульных данных.
- `tc_dlist` - intrusive doubly-linked list utility.
- `Settings` - JSON-backed settings API, доступный из C++/Python.
- `trent` - JSON/YAML/value tree utilities.
- `termin/geom/*` - базовые геометрические/value-типы: vectors, matrices,
  poses, quaternions, rays, AABB, colors, sizes, rectangles.
- `geom/tc_affine3.h` / `termin/geom/affine3.hpp` - exact
  double-precision `Basis3d` и `Affine3d`. Basis хранится тремя подряд идущими
  column vectors; affine добавляет translation и действует на column vector
  как `basis * point + translation`. Композиция `parent * child` сначала
  применяет child. Преобразование в 4x4 использует общий column-major
  OpenGL-style layout Termin.
- `termin/camera/orbit_camera.hpp` / `termin.geombase.OrbitCamera` - чистая математика orbit camera без ECS, UI и render backend.
- `tc_profiler` / `tcbase.profiler` - base-level profiler без зависимости от `termin-app`.
- input enums (`Action`, `MouseButton`, `Mods`, `Key`) для общего event vocabulary.
  `tcbase::MouseButton` / `tcbase.MouseButton` является единственным
  каноническим типом кнопки мыши: `NONE=-1`, `LEFT=0`, `RIGHT=1`,
  `MIDDLE=2`, `OTHER=3`. Platform и C ABI adapters сохраняют эти числовые
  значения, но не объявляют собственные engine-level enum-типы.

## Публичный API

C/C++ headers лежат в `include/tcbase/`, `include/tc_profiler.h`,
`include/termin/geom/` и `include/termin/camera/`.

`tc_tensor` описывает typed memory block/view: dtype, shape, byte strides,
optional owner/deleter и readonly flag. Это не math tensor library; конкретные
API должны явно решать, принимают ли strided view или требуют contiguous copy.

```cpp
#include <tcbase/tc_tensor.h>

size_t shape[2] = {vertex_count, 3};
tc_tensor positions = tc_tensor_empty();

if (tc_tensor_init_owned(&positions, TC_DTYPE_F32, 2, shape, 0)) {
    float* data = (float*)positions.data;
    data[0] = 1.0f;
}

tc_tensor_free(&positions);
```

Python API экспортируется из `tcbase`:

```python
import tcbase

tcbase.log.info("hello")
tcbase.log.capture_start(2048)
records, dropped_count = tcbase.log.capture_drain(512)
tcbase.log.capture_stop()
settings = tcbase.Settings("settings.json", True)
settings.set("ui/theme", "dark")
settings.save()
```

Native Editor владеет capture queue на протяжении editor session и является
pull-consumer. Стандартный Python `logging` подключается в редакторе handler-ом,
который переводит записи в `tc_log`; editor/build helpers также пишут через
`tcbase.log`. Поэтому единственный путь в Editor Console — native drain, а
stderr и platform callback остаются независимыми sinks. Перехват произвольных
`stdout`/`stderr` в этот контракт не входит.

## Когда использовать

Код можно переносить в `termin-base`, если он:

- не знает о конкретной domain-модели;
- не требует GPU, scene, mesh, renderer, UI или editor API;
- нужен нескольким нижним/средним модулям;
- может быть протестирован отдельно от основного приложения.

Если utility начинает знать о runtime lifecycle конкретного модуля, он должен остаться в этом модуле или переехать в более подходящий слой.

## Profiler timing vocabulary

`tc_frame_profile` хранит сырые, не сглаженные величины:

- `interval_ms` — start-to-start интервал между соседними кадрами;
- `active_ms` — wall-clock CPU duration между `begin_frame` и `end_frame`;
- `target_interval_ms` — целевой интервал scheduler-а;
- `deadline_lateness_ms` — насколько фактический старт опоздал относительно ожидаемого;
- `missed_intervals` — число полных target-интервалов в этом опоздании.

`total_ms` пока сохраняется как compatibility alias для `active_ms`. Разница
`interval_ms - active_ms` сама по себе не является чистым `sleep`: в ней могут
быть OS scheduling, presentation wait и другая работа между frame scopes.

История ограничена кольцевым буфером. Для последовательного потребления следует
использовать `tc_profiler_history_after` / `Profiler.history_after`: API исключает
открытый кадр и явно возвращает `dropped_count`, если cursor отстал от буфера.
