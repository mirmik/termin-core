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
- `tc_value` - C tagged-union value type для сериализации и межмодульных данных.
- `tc_dlist` - intrusive doubly-linked list utility.
- `Settings` - JSON-backed settings API, доступный из C++/Python.
- `trent` - JSON/YAML/value tree utilities.
- `termin/geom/*` - базовые геометрические типы: vectors, matrices, poses, quaternions, rays, AABB.
- `termin/camera/orbit_camera.hpp` / `termin.geombase.OrbitCamera` - чистая математика orbit camera без ECS, UI и render backend.
- `tc_profiler` / `tcbase.profiler` - base-level profiler без зависимости от `termin-app`.
- input enums (`Action`, `MouseButton`, `Mods`, `Key`) для общего event vocabulary.

## Публичный API

C/C++ headers лежат в `include/tcbase/`, `include/tc_profiler.h`,
`include/termin/geom/` и `include/termin/camera/`.

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
