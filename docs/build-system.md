# Система сборки

## Обзор

Проект — монорепозиторий из множества C/C++ библиотек с Python-биндингами. Каждая библиотека остаётся отдельным CMake-проектом со своим `CMakeLists.txt`, но основной SDK workflow собирается через корневой CMake-граф с `add_subdirectory()`.

Публичная точка входа для полной сборки — `./build-sdk.sh`. Скрипты стадий (`build-sdk-cpp.sh`, `build-sdk-bindings.sh`) конфигурируют один и тот же root build directory (`build/Release` для Release) и устанавливают результат в общую SDK-директорию (`./sdk/`). Это позволяет CMake параллелить независимые цели в рамках одного графа, а standalone-сборки отдельных модулей по-прежнему могут использовать установленные CMake package configs из `sdk/`.

Сборка через `./build-sdk.sh` проходит в четыре стадии:
1. **C/C++ библиотеки + Python bindings** — shared libraries, заголовки, CMake config, nanobind-модули и Python-исходники
2. **C# bindings** — на Windows включены по умолчанию, на Linux включаются флагом `--csharp` и требуют SWIG и `dotnet`; Linux-сборка содержит только `Termin.Native`, без WPF
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

Чтобы дополнительно собрать cross-platform C# bindings на Linux:

```bash
./build-sdk.sh --sdl --no-wheels --csharp
```

Для WPF/C# D3D11-профиля SDK собирается без SDL, Vulkan и legacy OpenGL. После C++ SDK стадии C# слой нужно собрать в Windows-only plot profile, чтобы в `sdk/csharp` попали только tcplot/WPF runtime DLL и D3D11 shader artifacts:

```powershell
.\build-sdk.ps1 --no-sdl --no-vulkan --no-opengl --no-wheels
.\build-sdk-csharp.ps1 --plot-d3d11 --no-sdl --no-vulkan --no-opengl
```

Профиль `plot-d3d11` генерирует C# API только для `tcplot`/`Termin.Wpf`, не копирует scene/render/component DLL и режет `share/termin` до D3D11 artifacts, нужных графикам.
`Termin.Wpf` собирается только Windows-скриптом и multitarget-ится под `netcoreapp3.1` и `net8.0-windows`. Управляемые сборки в SDK раскладываются по `sdk/csharp/lib/<tfm>/`; плоские `sdk/csharp/lib/*.dll` оставлены для старых потребителей и содержат `netcoreapp3.1`-вариант `Termin.Wpf`. Linux `build-sdk-csharp.sh` намеренно пакует только cross-platform `Termin.Native` и native runtime `.so`.

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
├── bin/            # Исполняемые файлы, включая termin_python; DLL на Windows
├── lib/            # Import libraries (.lib), shared libraries на Linux (.so), cmake configs
│   ├── cmake/      # find_package() конфиги для каждого модуля
│   └── python3.10/site-packages/
│       # Python-пакеты (native-модули + .py исходники) на Linux
├── include/        # C/C++ заголовки
└── python/Lib/site-packages/
    # Python-пакеты на Windows; Windows stdlib живёт в sdk/python/Lib/
```

### Артефактные manifests

Native Python artifacts имеют два разных schema-v2 контракта:

- `sdk/termin-artifacts.json` — поставляемый relocatable SDK manifest. Поле
  `path` всегда относительно корня SDK; entry фиксирует kind, extension,
  target, Python ABI, SHA-256 и bundled/external runtime dependencies. Manifest
  не содержит checkout, `build_dir`, `sdk_prefix` или других абсолютных путей.
- `build/<config>/termin-build-artifacts.json` — внутренний developer manifest
  с точными абсолютными путями build tree. Он не поставляется как часть SDK.

Оба manifest фиксируют content-derived `native_build_id`. Для SDK он вычисляется
из SHA-256 всех native extensions и транзитивно bundled shared libraries, а не
из mtimes. Этот ID становится PEP 440 suffix `+sdk<id>` и без пересчёта
используется runtime wheels, `python-runtime-manifest.json` и public
`sdk/wheels`. Повторный wheel-stage сохраняет ID, пока native payload не
изменился. Финальная SDK verification сопоставляет версии и байты native
payloads во всех трёх представлениях и отвергает stale или смешанный wheelhouse.

Setuptools consumer выбирает установленный контракт только через
`TERMIN_SDK=/path/to/sdk`. Явный build-tree режим включается через
`TERMIN_ARTIFACT_MANIFEST=/path/to/termin-build-artifacts.json`. После выбора
manifest никакого поиска в checkout, соседнем SDK, `/opt` или `PATH` нет:
отсутствующий artifact, выход path за корень SDK, неверные kind/target/ABI или
hash завершают сборку с ошибкой. Поэтому перенос SDK в другой каталог безопасен,
а stale build tree не может незаметно подменить поставляемый binary.

### Bundled Python и тестовый контур

`sdk/bin/termin_python` — SDK-relative isolated launcher. Он игнорирует
`PYTHONHOME`, `PYTHONPATH` и user site-packages, использует bundled stdlib и
site-packages, а `--termin-info` печатает диагностический JSON с SDK root,
Python ABI и активными путями.

Runtime population разделён на build и install:

- `build-system/python-sdk-build-requirements.txt` фиксирует инструменты
  disposable build environment `build/python-runtime/build-env`;
- `build-system/python-runtime-lock.txt` содержит exact pins для всех
  third-party distributions, поставляемых с SDK, включая `pytest` и его
  транзитивные зависимости;
- external wheels материализуются в `build/python-runtime/external-wheels`
  (sdist-only `pyassimp` собирается в wheel на этой стадии);
- все Termin wheels собираются из `build-system/packages.json` в
  `build/python-runtime/termin-wheels`;
- SDK `site-packages` очищается и устанавливается одним offline-проходом с
  `--no-index --no-deps`;
- `sdk/python-runtime-manifest.json` фиксирует Python ABI, lock hash, полный
  набор distributions и hashes их `RECORD`.

SDK verification сверяет manifest с фактическими metadata и payload hashes и
падает на лишнем, отсутствующем или изменённом distribution. Копирование
runtime-пакетов из host `site-packages` запрещено. После первичного заполнения
wheelhouse population можно проверить без сети:

```bash
TERMIN_PYTHON_RUNTIME_OFFLINE=1 \
  PYTHONPATH=termin-build-tools \
  python -m termin_build.sdk --repo-root . install-python
```

Developer/test environment не является вторым runtime venv. Команда

```bash
./setup-sdk-python-env.sh
```

создаёт disposable слой `build/python-envs/test`: pinned Ruff и прочие
test-only dependencies; `pytest` доступен прямо из bundled SDK. Затем создаётся
`overlay.json`. Manifest-driven finder загружает Python-исходники
Termin из checkout, но ищет native extensions прежде всего в соответствующем
SDK. Overlay привязан к hash `sdk/termin-artifacts.json` и Python ABI; устаревший
overlay завершается ошибкой вместо неявного смешивания сборок.

Прямые режимы запуска:

```bash
# Разработка и тесты из checkout поверх SDK runtime
sdk/bin/termin_python --termin-overlay build/python-envs/test/overlay.json -m pytest

# Проверка только установленного SDK, без checkout overlay
sdk/bin/termin_python -c "import tcbase, termin.engine"
```

Старые `setup-test-venv.*` и корневой `.venv` workflow удалены. Новый workflow
не копирует `.so`/`.pyd` в source tree и не требует `--force` после пересборки
bindings; после изменения SDK нужно лишь перегенерировать overlay.

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

Обе части устанавливаются в versioned `site-packages`: на Linux в
`lib/pythonX.Y/site-packages/<package>/`, на Windows в
`python/Lib/site-packages/<package>/`. Старое staging-дерево
`sdk/lib/python/termin/` удалено и не должно использоваться новыми install
rules.

```cmake
# Native-модуль
install(TARGETS _mylib_native DESTINATION lib/python${PYTHON_VERSION}/site-packages/termin/mylib)

# Python-исходники (без этого пакет не будет импортироваться!)
install(DIRECTORY python/termin/mylib/
    DESTINATION lib/python${PYTHON_VERSION}/site-packages/termin/mylib
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

Поэтому runtime-регистрация DLL должна добавлять директории с нативными библиотеками: package-local `lib/` для standalone pip-пакетов и `sdk/bin/`/`sdk/lib/` для SDK layout. SDL2 поставляется как нативная зависимость SDK; Python-код не должен загружать отдельный PySDL2 runtime.

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

> Архитектурное направление принято 2026-07-19: проверенное SDK install tree
> является единственным editor/launcher runtime artifact. `termin-app` —
> application product с внутренним Python payload, а не самостоятельный
> library wheel. Текущий `termin-app` wheel и host-derived standalone packager
> ещё существуют как незавершённая миграция; см.
> [протокол совета](architecture-council/2026-07-19-termin-app-product-boundary.md).

Launcher и editor — это C++ исполняемые файлы, которые встраивают Python-интерпретатор. При сборке с `BUNDLE_PYTHON=ON` в SDK копируется:
- Python stdlib (`python/Lib/` на Windows, `lib/pythonX.Y/` на Linux)
- Внешние pip-пакеты в `python/Lib/site-packages/` на Windows или
  `lib/pythonX.Y/site-packages/` на Linux
- DLL/so Python-рантайма

Launcher при запуске:
1. Определяет, есть ли bundled Python (ищет stdlib рядом с собой)
2. Если есть — вызывает `Py_SetPythonHome()` чтобы Python использовал bundled stdlib
3. Добавляет bundled `site-packages` в `sys.path`
4. Запускает Python-код приложения

Stage 3 SDK build устанавливает exact-locked runtime offline из подготовленного
wheelhouse и проверяет его через `python-runtime-manifest.json`. Копирование из
ambient host `site-packages` запрещено. При этом отдельный top-level
`termin-app` standalone path пока всё ещё читает host `sys.prefix`; этот
legacy path подлежит удалению согласно принятому решению.

Нижележащие library packages продолжают собираться отдельными wheels. В
частности, graphics/display/GUI subset должен устанавливаться из `sdk/wheels`
без `termin-app`; внешний Diffusion Editor является consumer gate этого
контракта.

---

## Project build profiles и runtime package gate

`termin_builder` является тонкой CLI-точкой входа для project build: он находит
project root и делегирует чтение, проверку и компиляцию профиля Python backend-у
`termin.project_build.profile_build`. C++ CLI и `termin_runner` не имеют
собственного JSON-представления схемы. Target-specific логика живет в Python
wrapper-ах для `desktop`, `android` и `quest_openxr`.

Schema-v2 и ее persistence API принадлежат toolkit-neutral модулю
`termin.project_build.profiles`. `BuildProfileStore` загружает и перечисляет
профили, разрешает project-relative пути и атомарно сохраняет детерминированный
JSON. Он принимает только `version: 2`, отклоняет v1 без runtime-миграции,
неизвестные поля и поля чужого target-варианта. Импорт profile store не
загружает argparse и target build wrappers, поэтому модель можно напрямую
использовать в editor UI.

Профиль состоит из:

- обязательных `configuration`, `target` и `content`;
- optional project-relative `output_dir`, по умолчанию `dist/<profile-name>`;
- target-варианта `desktop`, `android` или `quest_openxr`;
- `content.entry_scene` и явного списка корневых `content.scenes`;
- явных root-модулей, дополнительных Python requirements и resource includes;
- единственного ordered desktop-списка `runtime.backends`, который одновременно
  задает приоритет runtime backend-ов и семейства пакуемых shader artifacts.

Для desktop `target` обязательно задает `os` и `arch`. Android и Quest задают
ABI и числовой `ndk_api`, но не имеют конфигурируемого `runtime`: Vulkan/OpenXR
являются частью фиксированного product target. Пути к SDK, компиляторам, Gradle
и build scripts в профиль не входят; их передает локальный `ToolchainContext`.

Android и Quest/OpenXR остаются разными продуктами со своими Gradle-проектами,
manifest-ами и entry point-ами, но используют общий APK pipeline. Конфигурации
`dev` и `debug` запускают Gradle variant `debug`, а `release` — variant
`release`. Готовый artifact определяется по Gradle `output-metadata.json`,
включая проверку `applicationId`; фиксированное имя `app-debug.apk` не является
частью контракта.

Оба Android-family target-а читают один `application` из канонического
`project_settings/project.json`: base application ID, launcher label,
целочисленный Android version code и отображаемый version name. Новому проекту
эти поля записываются сразу; для старого проекта без блока `application`
детерминированный ID и label выводятся из имени проекта. Android и Quest одного
проекта намеренно используют одинаковую base identity; profile suffix пока не
добавляется, поскольку контракт одновременной установки вариантов не заявлен.
Явно заданные некорректные identity/version values отклоняются, а не
подменяются молча.

Release APK всегда должен быть подписан. Для обоих продуктов используются
одинаковые обязательные переменные окружения:

- `TERMIN_ANDROID_SIGNING_KEYSTORE` — путь к keystore;
- `TERMIN_ANDROID_SIGNING_KEY_ALIAS`;
- `TERMIN_ANDROID_SIGNING_STORE_PASSWORD`;
- `TERMIN_ANDROID_SIGNING_KEY_PASSWORD`.

При отсутствии любого параметра release build завершается до запуска Gradle с
явной диагностикой. Debug signing при этом остается штатным поведением Android
Gradle Plugin.

Парсер v2 представляет сцены, модули, Python requirements и resource includes
типизированными полями. Явные scene roots участвуют в build: exporter пакует
каждую выбранную сцену и объединяет найденные в них resource/shader
dependencies. Desktop build также строит единый индекс `.module`/`.pymodule`,
разрешает dependency-first closure из `content.modules` и пакует только его
Python packages, готовые native artifacts и requirements в `package/modules`.
`package/modules/modules.json` и `runtime.modules` в `app.json` фиксируют exact
roots и closure. Для Android/Quest выбранные project modules, а для всех
target-ов explicit dynamic resource roots пока завершаются diagnostic
`profile.feature_pending`, а не молча игнорируются.

Project-level defaults для окна standalone player хранятся в
`project_settings/project.json` в поле `player_window`:

```json
{
  "application": {
    "id": "com.example.game",
    "label": "Example Game",
    "version_code": 1,
    "version_name": "0.1.0"
  },
  "player_window": {
    "width": 1280,
    "height": 720,
    "fullscreen": true,
    "vsync": true
  }
}
```

Desktop bundle `app.json` записывает эти значения в `runtime.window`.
Python `termin.player` и C++ `termin_player` используют их как дефолт, а
CLI-флаги `--width`, `--height`, `--fullscreen` и `--windowed` остаются явными
override-ами для smoke/manual runs.
Поле `vsync` выбирает construction-time presentation mode окна: `true`
соответствует `VSync`, `false` — `Immediate`. Для старых project/app manifests
без этого поля сохраняется VSync-on поведение.
На D3D11 оба режима используют flip-model swapchain. `Immediate` разрешён
только при `DXGI_FEATURE_PRESENT_ALLOW_TEARING`: swapchain и каждый resize
сохраняют `DXGI_SWAP_CHAIN_FLAG_ALLOW_TEARING`, а present использует
`Present(0, DXGI_PRESENT_ALLOW_TEARING)`. Если capability отсутствует, player
завершается с явной ошибкой вместо неявного перехода обратно на VSync.

Для desktop profile `runtime.backends` одновременно задаёт набор поставляемых
shader artifact families и порядок выбора backend на целевой машине. Runtime
package export пишет артефакты только для запрошенных backend targets и
добавляет тот же ordered список в `target_requirements.backends`, а `app.json`
повторяет его как `runtime.backends`. Валидатор требует точного равенства списка
и shader artifact families. Packaged player проверяет равенство обоих
манифестов и пробует backend-ы по порядку только во время начального создания
graphics session/window, логируя каждую неудачу. `TERMIN_BACKEND`/`--backend`
выбирает ровно один packaged backend и запрещает fallback.

SDK записывает целевые `platforms.desktop.os` и `platforms.desktop.arch` в
`termin-sdk-capabilities.json`. Desktop preflight отклоняет SDK, target которого
не совпадает с typed profile; `app.json` и runtime package manifest повторяют
согласованные `os/arch`, поэтому host defaults не могут незаметно изменить
profile intent.
D3D11-артефакты генерируются как `shaders/d3d11/<uuid>.vs.cso` /
`shaders/d3d11/<uuid>.ps.cso` и остаются opt-in, чтобы обычные Linux/Android
сборки не требовали Windows SDK `fxc`.

`content.resources.policy: strict` является default contract для packaged build.
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

Runtime package manifest schema v2 задаёт multi-scene contract явно:

```json
{
  "version": 2,
  "entry_scene": "Scenes/Main.scene",
  "scenes": [
    {
      "identity": "Scenes/Main.scene",
      "path": "scenes/Scenes/Main.scene.json"
    },
    {
      "identity": "Scenes/Menu.scene",
      "path": "scenes/Scenes/Menu.scene.json"
    }
  ],
  "resources": []
}
```

`identity` — нормализованный project-relative путь исходной `.scene`; он
остаётся стабильным после переноса bundle. `path` указывает только внутрь
package. `entry_scene` обязан присутствовать в таблице. Валидатор проверяет
каждую сцену и полный объединённый resource closure, а native runtime загружает
и регистрирует всю таблицу; player запускает entry scene и оставляет остальные
сцены неактивными до явного перехода через `SceneManager`.

Desktop target packaging больше не должен копировать SDK `site-packages`
целиком по умолчанию. В `minimal_strict` bundle получает Python stdlib из SDK
без `site-packages`, затем создаёт чистый `site-packages` и добавляет только
явный Termin player runtime seed плюс requirements из выбранного module closure
и профиля.
Состав записывается в `python-runtime.json`. Если временно нужен старый broad
copy для диагностики, профиль должен явно указать:

```json
"runtime": {
  "backends": ["vulkan", "opengl"],
  "python_package_policy": "sdk_broad_copy"
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
- tgfx2 тесты подключены к CTest и являются частью основного C++ test workflow;
  backend-independent проверки вроде `tgfx2_sdf_test` остаются в обычном
  headless наборе, а тесты, создающие окна/GL-контексты, включаются только
  через `--window-tests` / `--full`.

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

Python suite roots больше не перечисляются в `run-tests-python.sh` и
`run-tests-python.ps1`. Их source of truth — `build-system/test-suites.json`.
Локальные runners вызывают `termin_build.repository_control`: профиль `pr`
применяет pytest-выражение `not full`, а `linux-full` и `windows-d3d11`
снимают этот фильтр на соответствующей платформе. Каждая suite запускается
отдельно; planner продолжает прогон после ошибки и печатает общий список
упавших suites.

Проверка manifests и orphan-test gate не требует запуска самих тестов:

```bash
PYTHONPATH=termin-build-tools \
python3 -m termin_build.repository_control --repo-root . check
```

Gate сканирует repository-owned `test_*.py` и `*_test.py`. Каждый найденный
файл обязан принадлежать ровно одному объявленному pytest root. Generated,
SDK, venv и third-party roots исключены явно в manifest. План можно проверить
до исполнения:

```bash
PYTHONPATH=termin-build-tools \
python3 -m termin_build.repository_control --repo-root . \
plan pr --platform linux --json
```

Команда `plan --json` выдаёт канонический expected manifest
`termin-test-expected` для текущего checkout, profile и platform. Поле `suites`
содержит применимые suites, а `inapplicable` — неприменимые suites с
детерминированной причиной несовпадения profile/platform. `fingerprint` —
SHA-256 канонического содержимого manifest; executor result принимается только
для того expected manifest, fingerprint которого он явно указывает. Поэтому
manifest с другим test inventory нельзя случайно принять за результат текущего
набора.

Каждый естественный executor (`pytest`, `ctest`, `process-smoke`) формирует
отдельный `termin-test-execution` manifest и не передаёт управление тестами
универсальному runner. Общий suite-level контракт содержит:

- `executor`, `profile`, `platform` и `expected_fingerprint`;
- `selected` — suites, которые adapter принял к исполнению;
- ровно один terminal outcome для каждой применимой suite: `executed`,
  `skipped` или `failed`;
- обязательную непустую `reason` для каждого `skipped` outcome;
- executor-specific подробности, например CTest registrations или pytest
  diagnostics, в необязательном `details`, не меняющем suite-level результат.

`missing` не записывается самим executor: его вычисляет verifier как разность
между locally computed expected coverage и terminal outcomes. Это не позволяет
сломавшемуся adapter объявить потерянную suite корректно обработанной.
Неизвестная suite, несовпадающий fingerprint, отсутствие selection/result,
`failed`, дублирующий outcome или skip без причины делают verification красной.
Неприменимые suites учитываются из expected manifest и уже несут валидированную
причину.

Несколько независимых execution manifests проверяются одной командой:

```bash
sdk/bin/termin_python -m termin_build.repository_control \
  verify-execution \
  --expected build/expected-pr-linux.json \
  --manifest build/python-execution-manifest.json \
  --manifest build/ctest-execution-manifest.json
```

Команда возвращает ненулевой exit code при неполном или неуспешном покрытии и
печатает `termin-test-verification` report с `selected`, `executed`, `skipped`,
`failed`, `missing`, `inapplicable` и неожиданными результатами. Адаптеры и
canonical runners строят selection непосредственно из manifest текущего
checkout. Они не принимают внешний `--plan-file` и не поддерживают неявный
subset/sharding: отдельный job не может подменить локально применимый набор
suites устаревшим artifact. CI сохраняет и передаёт между jobs только execution
manifests; verification job заново вычисляет expected manifest из своего
checkout и сравнивает с fingerprints executor results. CTest adapter агрегирует
registration-level JUnit outcomes в suite-level `termin-test-execution`, сохраняя
исходные registrations и причины skip/failure в `details`.

Focused-вызов `run-tests-python.* <pytest-target ...>` остаётся прямым pytest
запуском и не меняет repository inventory.

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
- [ ] Добавить модуль в `build-system/packages.json` в правильное место для pip/package workflow, если модуль имеет Python-пакет
- [ ] Добавить модуль в корневой `CMakeLists.txt`, если он должен участвовать в SDK build graph
