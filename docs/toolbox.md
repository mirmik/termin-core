# Что в чемодане

Core лучше понимать не как одну библиотеку, а как несколько маленьких
договорённостей, собранных в один проверяемый SDK. Они живут вместе потому,
что должны одинаково выглядеть для всех доменных репозиториев Termin.

## termin-base: пол, стены и рулетка

`termin-base` содержит вещи, которым нельзя знать, что такое сцена или
редактор:

- C/C++ logging и bounded capture queue;
- UUID, строки, handles, pools и resource map;
- `tc_value` и Trent для value trees, JSON и YAML;
- ABI-friendly `tc_tensor` для typed strided memory;
- настройки;
- векторы, матрицы, poses, quaternions, AABB, spatial algebra;
- чистую математику orbit camera;
- низкоуровневый profiler.

Здесь намеренно соседствуют C ABI и удобный C++ слой. C API держит границу
стабильной, C++ API убирает лишний шум, Python bindings дают те же базовые
понятия инструментам и тестам.

```python
import tcbase

tcbase.log.info("сообщение из Python прошло через общий лог")

settings = tcbase.Settings("settings.json", True)
settings.set("tools/last_run", "successful")
settings.save()
```

Подробности: [документ модуля в репозитории][base-doc].

## termin-dispatch: очередь без скрытого правительства

Dispatcher принимает работу из разных потоков, но не создаёт собственный
поток и не назначает себя главным. Callback исполняется только при явном
`drain()` или `run_pending()`.

Это полезный, почти скучный контракт. Producer может сказать «сделай потом»,
а владелец приложения решает, где именно находится это «потом»: начало кадра,
конец транзакции, idle phase или тестовый метод.

Успешная публикация передаёт dispatcher-у владение payload. Tickets защищены
generation, поэтому вчерашняя отмена не попадёт в сегодняшнюю задачу, занявшую
тот же slot.

Подробности: [C, C++ и Python API dispatcher-а][dispatch-doc].

## termin-inspect: таможня типов

Inspect связывает три мира:

- C dispatcher задаёт language-neutral операции;
- C++ registries знают поля, наследование и kind handlers;
- Python bridge регистрирует Python-классы и преобразования.

Задача не в том, чтобы превратить C++ в динамический язык. Задача — дать
редактору, сериализатору и инструментам один явный способ спросить объект о
полях и значениях, не подменяя lifetime и ownership догадками.

У `termin-inspect` уже есть собственный подробный маршрут: быстрый старт,
архитектура, kind system, inheritance, Python bridge и gotchas. Начните с
[его главной страницы][inspect-doc].

## Python host: один интерпретатор, одна история

`termin-python-host` и `termin_python` отвечают за изолированный запуск
канонического CPython:

- конфигурацию через современный `PyConfig`;
- Python home и `sys.argv` до инициализации;
- проверку runtime ABI против headers и SOABI сборки;
- явный lifecycle для тестов и короткоживущих процессов.

Host не владеет editor state, scene state или Python callbacks продукта.
Конкретное приложение обязано освободить свои объекты до финализации
интерпретатора. Core предоставляет границу, но не изображает из себя хозяина
всего процесса.

## nanobind SDK: прекращение ABI-анархии

Каждый Python extension мог бы собирать свою копию nanobind runtime и надеяться,
что всё совпадёт. Core выбирает менее азартный путь: один `nanobind-ft`, один
CPython 3.14t ABI и CMake package, который отвергает несовместимого consumer-а
до того, как тот превратится в загадочный crash.

Для CMake consumer-а это выглядит обычно:

```cmake
find_package(Python 3.14 EXACT REQUIRED
    COMPONENTS Interpreter Development.Module)
find_package(nanobind CONFIG REQUIRED)
nanobind_add_module(my_module NB_SHARED module.cpp)
```

Free-threaded профиль и общая runtime library добавляются контрактом SDK.

## termin-mcp: связь без знания о мире

MCP-слой предоставляет защищённый JSON-RPC server, выполнение Python через
явно переданный host context и SDK-scoped session discovery. Он не знает, что
такое сцена, asset manager или editor selection. Эти значения может передать
конкретный host — сознательно и под своим именем.

Это различие удерживает протокол в Core, а власть над приложением оставляет
приложению.

## termin-build-tools: машина под половицами

Этим пакетом редко пользуются во время работы приложения. Он готовит pinned
Python, строит wheels, пишет manifests, проверяет hashes и ABI, собирает SDK и
испытывает его после relocation.

Если остальные модули — инструменты в чемодане, то `termin-build-tools` —
человек, который сверяет опись, запирает чемодан и бросает его с лестницы,
чтобы убедиться, что замки настоящие.

[base-doc]: https://github.com/mirmik/termin-core/blob/master/termin-base/docs/index.md
[dispatch-doc]: https://github.com/mirmik/termin-core/blob/master/termin-dispatch/docs/index.md
[inspect-doc]: https://github.com/mirmik/termin-core/blob/master/termin-inspect/docs/index.md
