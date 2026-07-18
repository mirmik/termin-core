# termin-base / tcbase

`termin-base` содержит базовые типы и утилиты, на которые могут опираться остальные библиотеки Termin без зависимости от scene/render/gui/application слоев.

Python-пакет: `tcbase`.

Связанные документы:

- [Module Map](../../docs/modules.md#termin-base--tcbase)
- [Build system](../../docs/build-system.md)
- [Canonical naming](../../docs/architecture/2026-03-15-canonical-naming.md)

## Основные области

- `tc_log` - общий C/C++ logging API.
- `tc_pool` - handle/generation pool primitive.
- `tc_resource_map` - generic resource map.
- `tc_tensor` - ABI-friendly typed strided memory descriptor для bulk buffers.
- `tc_value` - C tagged-union value type для сериализации и межмодульных данных.
- `tc_dlist` - intrusive doubly-linked list utility.
- `Settings` - JSON-backed settings API, доступный из C++/Python.
- `trent` - JSON/YAML/value tree utilities.
- `termin/geom/*` - базовые геометрические/value-типы: vectors, matrices,
  poses, quaternions, rays, AABB, colors, sizes, rectangles.
- `termin/camera/orbit_camera.hpp` / `termin.geombase.OrbitCamera` - чистая математика orbit camera без ECS, UI и render backend.
- `tc_profiler` / `tcbase.profiler` - base-level profiler без зависимости от `termin-app`.
- input enums (`Action`, `MouseButton`, `Mods`, `Key`) для общего event vocabulary.

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
settings = tcbase.Settings("settings.json", True)
settings.set("ui/theme", "dark")
settings.save()
```

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
