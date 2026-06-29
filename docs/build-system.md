# Система сборки

## Обзор

Проект — монорепозиторий из множества C/C++ библиотек с Python-биндингами. Каждая библиотека остаётся отдельным CMake-проектом со своим `CMakeLists.txt`, но основной SDK workflow собирается через корневой CMake-граф с `add_subdirectory()`.

Публичная точка входа для полной сборки — `./build-sdk.sh`. Скрипты стадий (`build-sdk-cpp.sh`, `build-sdk-bindings.sh`) конфигурируют один и тот же root build directory (`build/Release` для Release) и устанавливают результат в общую SDK-директорию (`./sdk/`). Это позволяет CMake параллелить независимые цели в рамках одного графа, а standalone-сборки отдельных модулей по-прежнему могут использовать установленные CMake package configs из `sdk/`.

Сборка через `./build-sdk.sh` проходит в четыре стадии:
1. **C/C++ библиотеки + Python bindings** — shared libraries, заголовки, CMake config, nanobind-модули и Python-исходники
2. **C# bindings** (опционально, требует SWIG)
3. **Bundled Python site-packages** — установка Python-пакетов в bundled runtime SDK
4. **SDK Python wheelhouse** — сборка `sdk/wheels` (отключается через `--no-wheels`)

Внутри root build зависимости между модулями выражены CMake targets. Для standalone-сборок модулей остаётся путь через `find_package()` и `CMAKE_PREFIX_PATH=sdk/`.

Типичная сборка SDK:

```bash
./build-sdk.sh --sdl
```

Если wheelhouse `sdk/wheels` не нужен для текущей итерации, его сборку можно
отключить:

```bash
./build-sdk.sh --sdl --no-wheels
```

Для WPF/C# D3D11-профиля SDK собирается без SDL, Vulkan и legacy OpenGL. После C++ SDK стадии C# слой нужно собрать в Windows-only plot profile, чтобы в `sdk/csharp` попали только tcplot/WPF runtime DLL и D3D11 shader artifacts:

```powershell
.\build-sdk.ps1 --no-sdl --no-vulkan --no-opengl --no-wheels
.\build-sdk-csharp.ps1 --plot-d3d11 --no-sdl --no-vulkan --no-opengl
```

Профиль `plot-d3d11` генерирует C# API только для `tcplot`/`Termin.Wpf`, не копирует scene/render/component DLL и режет `share/termin` до D3D11 artifacts, нужных графикам.

Только C/C++ стадия:

```bash
./build-sdk-cpp.sh --sdl
```

Только Python/nanobind bindings:

```bash
./build-sdk-bindings.sh --sdl
```

Прямой CMake-вариант:

```bash
cmake -S . -B build/Release \
  -DCMAKE_BUILD_TYPE=Release \
  -DTERMIN_BUILD_PYTHON=ON \
  -DTERMIN_ENABLE_VULKAN=ON \
  -DTERMIN_ENABLE_SDL=ON
cmake --build build/Release --parallel
cmake --install build/Release
```

### Ускорение C/C++ компиляции

Root CMake-граф поддерживает несколько ускорителей сборки:

- `ccache` включается автоматически, если бинарь найден в `PATH`. Отключение: `--no-ccache` или `-DTERMIN_USE_CCACHE=OFF`.
- Для новых build-dir shell-скрипты по умолчанию оставляют CMake default generator. `Ninja` включается явно через `--ninja`, `TERMIN_CMAKE_GENERATOR=Ninja` или `CMAKE_GENERATOR_NAME=Ninja`. Уже существующий build-dir не меняет генератор; для смены генератора нужен `--clean` или новый `BUILD_DIR`.
- `BUILD_JOBS=<N>` задаёт параллелизм для `cmake --build`.
- `--unity` включает CMake unity build для выбранных C++-тяжёлых целей. Флаг экспериментальный и не включён по умолчанию.
- `--pch` включает precompiled headers для выбранных C++-тяжёлых целей и включён по умолчанию. Отключение: `--no-pch` или `-DTERMIN_ENABLE_PCH=OFF`. C++-тяжёлые runtime-библиотеки (`termin_engine`, `termin_navmesh_components`) сохраняют свой локальный PCH.
- Глобальный CMake unity build (`-DCMAKE_UNITY_BUILD=ON`) поддерживается для root graph после cleanup внутренних helper/state имён. Vendored `Recast`/`Detour` targets явно собираются без unity.

Примеры:

```bash
BUILD_JOBS=8 ./build-sdk-cpp.sh --sdl
BUILD_DIR=build/Release-ninja ./build-sdk-cpp.sh --sdl --ninja
BUILD_DIR=build/Release-unity ./build-sdk-cpp.sh --sdl --unity
BUILD_DIR=build/Release-no-pch ./build-sdk-cpp.sh --sdl --no-pch
```

PowerShell SDK-скрипты на Windows используют тот же root CMake graph:

```powershell
$env:BUILD_JOBS=8; .\build-sdk-cpp.ps1 --sdl
$env:BUILD_DIR="build\Release-unity"; .\build-sdk-cpp.ps1 --sdl --unity
$env:BUILD_DIR="build\Release-no-pch"; .\build-sdk-cpp.ps1 --sdl --no-pch
```

На Windows PowerShell-скрипты по умолчанию не выбирают Ninja автоматически и оставляют CMake default generator (обычно Visual Studio/MSVC). Ninja можно включить явно через `$env:TERMIN_CMAKE_GENERATOR="Ninja"`, но тогда CMake возьмёт компилятор из окружения/PATH; старый LLVM `clang-cl` может быть несовместим с текущим MSVC STL.

Прямой CMake-вариант:

```bash
cmake -S . -B build/Release-unity -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DTERMIN_ENABLE_VULKAN=ON \
  -DTERMIN_ENABLE_SDL=ON \
  -DTERMIN_USE_CCACHE=ON \
  -DTERMIN_ENABLE_UNITY_BUILD=ON \
  -DTERMIN_ENABLE_PCH=ON
cmake --build build/Release-unity --parallel 8
```

Script-level `--unity` intentionally applies only to selected targets where it has been checked for developer iteration: `termin_graphics2`, `termin_render`, `termin_engine`, `trent`. For a full audit/experiment use direct CMake with `-DCMAKE_UNITY_BUILD=ON`.

Script-level `--pch` applies to selected C++ targets with broad STL-heavy include usage: `termin_graphics2`, `termin_render`, `termin_engine`, `trent`, `tcplot`. It deliberately avoids C-only libraries and third-party vendored targets.

---

## Структура SDK

```
sdk/
├── bin/            # Исполняемые файлы + shared libraries на Windows (.dll)
├── lib/            # Import libraries (.lib), shared libraries на Linux (.so), cmake configs
│   ├── cmake/      # find_package() конфиги для каждого модуля
│   └── python/     # Python-пакеты (native-модули + .py исходники)
├── include/        # C/C++ заголовки
└── Lib/            # Bundled Python stdlib + site-packages (при BUNDLE_PYTHON=ON)
```

---

## Куда что ставится

### C/C++ библиотеки

На **Linux** shared library (`.so`) — это одновременно и библиотека для линковки, и файл, загружаемый в runtime. Она ставится в `lib/`.

На **Windows** shared library разделяется на два файла:
- **Import library** (`.lib`) — используется при компиляции/линковке → ставится в `lib/`
- **DLL** (`.dll`) — загружается в runtime → ставится в `bin/`

В CMake это контролируется тремя строками install:

```cmake
install(TARGETS mylib
    LIBRARY DESTINATION lib    # .so на Linux
    ARCHIVE DESTINATION lib    # .lib на Windows (и .a для статических)
    RUNTIME DESTINATION bin    # .dll на Windows
)
```

`RUNTIME DESTINATION` на Linux игнорируется для shared libraries (`.so` — это LIBRARY, не RUNTIME). Но на Windows DLL — это именно RUNTIME-артефакт. Если по ошибке указать `RUNTIME DESTINATION lib`, DLL окажется в `lib/` и не будет найдена при запуске.

### Python-пакеты

Python-пакет состоит из двух частей:
- **Native-модуль** (`.pyd` на Windows, `.so` на Linux) — компилированный C++ код
- **Python-исходники** (`.py`) — `__init__.py`, обёртки, утилиты

Порядок установки SDK-пакетов и canonical internal distribution names живут в
`build-system/packages.json`. Политика именования и полный инвентарь
`repo path / distribution / import namespace` описаны в
[Python Package Naming](./python-package-naming.md). В `install_requires` нужно
указывать distribution name из manifest (`tgfx`, `tmesh`, `tcbase`, ...), а не
repo path (`termin-graphics`, `termin-mesh`, `termin-base`) и не случайный
import namespace.

Обе части устанавливаются в `lib/python/<package>/` или `lib/python/termin/<package>/`:

```cmake
# Native-модуль
install(TARGETS _mylib_native DESTINATION lib/python/termin/mylib)

# Python-исходники (без этого пакет не будет импортироваться!)
install(DIRECTORY python/termin/mylib/
    DESTINATION lib/python/termin/mylib
    PATTERN "__pycache__" EXCLUDE
    PATTERN "*.pyc" EXCLUDE
)
```

### Заголовки

Заголовки ставятся в `include/`. Каждый модуль устанавливает свою поддиректорию.

### CMake configs

Каждый модуль генерирует CMake config в `lib/cmake/<module>/`, что позволяет downstream-модулям делать `find_package(<module> REQUIRED)`.

---

## Экспорт символов на Windows

На Linux все символы shared library видны по умолчанию. На Windows — наоборот: ничего не экспортируется, пока явно не указано.

Для этого используются макросы `__declspec(dllexport)` (при сборке библиотеки) и `__declspec(dllimport)` (при использовании). Переключение происходит через compile definition, который определяется только при сборке самой библиотеки (`PRIVATE`).

В проекте два уровня:

1. **C API** — единый макрос `TC_API`, переключается через `TC_EXPORTS`. Каждая библиотека, экспортирующая C-функции через `TC_API`, должна определять `TC_EXPORTS` в своих compile definitions.

2. **C++ классы** — каждая библиотека определяет свой макрос (например `MYLIB_API`), переключаемый через свой define (например `MYLIB_EXPORTS`). Это нужно потому что один модуль может экспортировать свои классы и одновременно импортировать классы из зависимостей.

`WINDOWS_EXPORT_ALL_SYMBOLS` считается временным миграционным механизмом для старых целей. Новые и обновляемые библиотеки должны экспортировать публичный ABI через явные `*_API`/`TC_API` макросы, иначе CMake начинает экспортировать лишние C++-символы вроде vtable/RTTI и на MSVC появляются дублирующиеся export-spec warnings.

На Linux оба макроса раскрываются в пустую строку (или `__attribute__((visibility("default")))`), поэтому ошибки экспорта на Linux не проявляются — они видны только при сборке на Windows.

---

## Поиск DLL в runtime

### Linux

Используется RPATH — путь поиска shared libraries, зашитый в ELF-бинарь. Настраивается через cmake-хелперы из `cmake/TerminRpath.cmake`. Типичный RPATH: `$ORIGIN` (директория самого бинаря) + `${CMAKE_INSTALL_PREFIX}/lib`.

### Windows

Windows не использует RPATH. Начиная с Python 3.8, DLL ищутся только:
- В директории исполняемого файла
- В директориях, явно зарегистрированных через `os.add_dll_directory()`
- В системных директориях

Переменная `PATH` по умолчанию **не используется** для поиска DLL в Python 3.8+.

Поэтому runtime-регистрация DLL должна добавлять директории с нативными библиотеками: package-local `lib/` для standalone pip-пакетов и `sdk/bin/`/`sdk/lib/` для SDK layout. Для сторонних библиотек вроде SDL2 дополнительно выставляются env-переменные (например `PYSDL2_DLL_PATH`).

---

## Сборка Python bindings

### Принцип разделения

C++ часть каждого модуля полностью самодостаточна и не зависит от Python. Флаг `-DTERMIN_BUILD_PYTHON=ON` добавляет дополнительные targets (nanobind-модули), но **не изменяет основную C++ библиотеку** — ни её исходники, ни compile definitions, ни зависимости. Python bindings пристраиваются сбоку, линкуясь к уже собранной библиотеке.

Это означает, что при переключении `TERMIN_BUILD_PYTHON` с OFF на ON основная библиотека не пересобирается — cmake инкрементально добавляет только новые targets.

### Две стадии сборки

Сборка разделена на две стадии (C++ → bindings) не потому что они конфликтуют, а для практического удобства: если Python или nanobind не установлены, хотя бы C++ часть соберётся. Технически можно собирать всё сразу с `-DTERMIN_BUILD_PYTHON=ON` — результат будет идентичным для SDK layout.

Обе стадии используют один и тот же build directory (`build/Release`). Вторая стадия переконфигурирует cmake, но благодаря инкрементальности C++ часть не пересобирается.

### Структура модуля с биндингами

Биндинги строятся через [nanobind](https://github.com/wjakob/nanobind). Каждый модуль может опционально собирать Python-расширение при `-DTERMIN_BUILD_PYTHON=ON`.

В SDK build project-модули используют shared `libnanobind.so` (`NB_SHARED`), чтобы не собирать отдельный `nanobind-static` для каждого набора биндингов.

```
mylib/
├── CMakeLists.txt
├── src/                    # C/C++ исходники библиотеки
├── include/                # Заголовки
└── python/
    ├── bindings/           # C++ код биндингов (nanobind)
    └── termin/mylib/       # Python-исходники пакета
        ├── __init__.py
        └── utils.py
```

---

## Bundled Python

Launcher и editor — это C++ исполняемые файлы, которые встраивают Python-интерпретатор. При сборке с `BUNDLE_PYTHON=ON` в SDK копируется:
- Python stdlib (`Lib/` на Windows, `lib/pythonX.Y/` на Linux)
- Внешние pip-пакеты в `Lib/site-packages/`
- DLL/so Python-рантайма

Launcher при запуске:
1. Определяет, есть ли bundled Python (ищет stdlib рядом с собой)
2. Если есть — вызывает `Py_SetPythonHome()` чтобы Python использовал bundled stdlib
3. Добавляет `lib/python/` и `Lib/site-packages/` в `sys.path`
4. Запускает Python-код приложения

Текущий Stage 3 SDK build использует активный host Python и не полностью
изолирован от его `site-packages`. Анализ риска и рекомендации по исправлению:
`docs/analysis/2026-06-08-sdk-python-host-environment-leakage.md`.

---

## Project build profiles и runtime package gate

`termin_builder` является тонкой CLI-точкой входа для project build: он находит
project root, читает `project_settings/build_profiles.json`, выбирает профиль и
передает сборку в Python backend `termin.project_build.profile_build`.
Target-specific логика живет в Python wrapper-ах для `desktop`, `android` и
`quest_openxr`.

Build profile schema version сейчас `1`. Профиль обязан задавать:

- `target`: `desktop`, `android` или `quest_openxr`;
- `entry_scene`: путь к `.scene` внутри project root;
- `output_dir`: директорию результата сборки.

Дополнительные нормализованные policy-поля:

- `configuration`: `dev`, `debug`, `release`; default `dev`;
- `resource_policy`: `strict`, `dev_smoke`; default `strict`.
- `shader_targets`: optional list из `vulkan`, `opengl`, `d3d11`.
- `python.package_policy`: для desktop optional policy упаковки Python runtime:
  `minimal_strict` по умолчанию или временный legacy opt-in `sdk_broad_copy`.
- `python.requirements`: optional list дополнительных Python distributions для
  desktop runtime; они объединяются с requirements из `.pymodule`.

Project-level defaults для окна standalone player хранятся в
`project_settings/project.json` в поле `player_window`:

```json
{
  "player_window": {
    "width": 1280,
    "height": 720,
    "fullscreen": true
  }
}
```

Desktop bundle `app.json` записывает эти значения в `runtime.window`.
Python `termin.player` и C++ `termin_player` используют их как дефолт, а
CLI-флаги `--width`, `--height`, `--fullscreen` и `--windowed` остаются явными
override-ами для smoke/manual runs.

Если `shader_targets` задан, runtime package export пишет артефакты только для
запрошенных backend targets и добавляет их в `target_requirements` manifest-а.
D3D11-артефакты генерируются как `shaders/d3d11/<uuid>.vs.cso` /
`shaders/d3d11/<uuid>.ps.cso` и остаются opt-in, чтобы обычные Linux/Android
сборки не требовали Windows SDK `fxc`.

`resource_policy: strict` является default contract для packaged build.
Отсутствующие mesh/material resources становятся build diagnostics уровня
`error`; exporter не пишет placeholder artifacts и не добавляет synthetic
resource entries в manifest. Placeholder/fallback artifacts разрешены только
при явном `resource_policy: dev_smoke` и сопровождаются diagnostics уровня
`warning`.

Единый Python pipeline выполняет:

```text
project preflight
-> target preflight
-> output preparation
-> runtime package export
-> runtime package validation
-> target packaging
```

Runtime package validation является gate перед target packaging. Если export
или validation вернули diagnostic с `level == "error"`, target packaging не
запускается: desktop bundle/APK не должны создаваться из заведомо битого
runtime package. CLI backend печатает diagnostics и возвращает non-zero exit
code при `error` diagnostics.

Desktop target packaging больше не должен копировать SDK `site-packages`
целиком по умолчанию. В `minimal_strict` bundle получает Python stdlib из SDK
без `site-packages`, затем создаёт чистый `site-packages` и добавляет только
явный Termin player runtime seed плюс requirements из `.pymodule`/профиля.
Состав записывается в `python-runtime.json`. Если временно нужен старый broad
copy для диагностики, профиль должен явно указать:

```json
"python": {
  "package_policy": "sdk_broad_copy"
}
```

---

## Компонентные библиотеки

Для однотипных компонентных модулей есть cmake-хелпер `TerminModule.cmake` с макросом `termin_add_module()`. Он автоматизирует создание shared library, настройку экспортов, RPATH и install-правил.

---

## C/C++ тесты

C/C++ тесты собираются через root CMake graph:

```bash
bash run-tests-cpp.sh
```

Флаги:

- без флагов запускается рабочий набор CTest без тестов, создающих окна;
- `--full` включает полный C++ набор, включая window/video backend tests;
- `--vulkan` / `--no-vulkan` управляют `TERMIN_ENABLE_VULKAN`; Vulkan
  включён по умолчанию и является основным тестовым путём;
- `--window-tests` / `--no-window-tests` точечно управляют тестами, которым нужен windowing/video backend;
- tgfx2 тесты подключены к CTest и являются частью основного C++ test workflow.

Window tests настроены так, чтобы пропускаться в headless-окружении без usable video backend, а не валить весь прогон.

## Общий тестовый цикл

Центральная точка проверки репозитория:

```bash
./run-tests.sh
```

По умолчанию это рабочий набор: C/C++ tests без window tests, Python tests без
тестов с маркером `full`, без editor-process smoke. Полный набор запускается
явно:

```bash
./run-tests.sh --full
```

Полный набор дополнительно запускает editor-process smoke tests для hot reload
модулей:

- `scripts/smoke-python-module-hot-reload`
- `scripts/smoke-cpp-module-cascade-hot-reload`

На headless Linux smoke-скрипты используют `xvfb-run`, если display не
настроен. Для полного прогона без editor MCP стадии:

```bash
./run-tests.sh --full --no-editor-smoke
```

Повторяемая матрица targeted smoke-checks для render/shader/backend/runtime
изменений описана в [Smoke Checks](smoke-checks.md).

---

## Портабельность

Некоторые POSIX-функции (например `strdup`) считаются устаревшими в MSVC. Для них используются портабельные обёртки (`tc_strdup`), которые на Windows вызывают `_strdup`, а на Linux — оригинальный `strdup`.

MSVC-специфичные warnings (C4251 — STL-члены в dllexport-классах, C4275 — не-dllexport базовый класс) подавляются через `/wd4251 /wd4275`. Они безопасны при условии, что вся сборка использует один и тот же CRT.

---

## Чеклист для нового модуля

- [ ] C/C++ экспорт: определить `TC_EXPORTS` (и свой `*_EXPORTS` для C++ классов)
- [ ] Install: `RUNTIME DESTINATION` в `bin`, не в `lib`
- [ ] MSVC: подавить C4251/C4275, добавить `_CRT_SECURE_NO_WARNINGS`
- [ ] RPATH: использовать хелперы из `cmake/TerminRpath.cmake`
- [ ] Python: установить и `.pyd`/`.so`, и `.py` файлы
- [ ] Добавить в `modules.conf` в правильное место для pip/package workflow, если модуль имеет Python-пакет
- [ ] Добавить модуль в корневой `CMakeLists.txt`, если он должен участвовать в SDK build graph
