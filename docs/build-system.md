# Система сборки

## Обзор

Проект — монорепозиторий из множества C/C++ библиотек с Python-биндингами. Каждая библиотека — отдельный CMake-проект со своим `CMakeLists.txt`. Библиотеки собираются последовательно и устанавливаются в общую SDK-директорию (`./sdk/`). Порядок сборки и зависимости описаны в `modules.conf`.

Сборка проходит в три стадии:
1. **C/C++ библиотеки** — shared libraries, заголовки, CMake config
2. **Python bindings** — nanobind-модули + Python-исходники
3. **C# bindings** (опционально, требует SWIG)

Каждый модуль собирается отдельным вызовом `cmake` с `CMAKE_INSTALL_PREFIX=sdk/` и `CMAKE_PREFIX_PATH=sdk/`. Это позволяет каждому следующему модулю находить уже установленные зависимости через `find_package()`.

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

Обе части устанавливаются в `lib/python/<package>/`:

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

Поэтому в проекте есть модуль `_dll_setup.py`, который импортируется первым и регистрирует нужные директории (`sdk/bin/`, `sdk/lib/python/termin/`) через `os.add_dll_directory()`. Для сторонних библиотек вроде SDL2 дополнительно выставляются env-переменные (например `PYSDL2_DLL_PATH`).

---

## Сборка Python bindings

### Принцип разделения

C++ часть каждого модуля полностью самодостаточна и не зависит от Python. Флаг `-DTERMIN_BUILD_PYTHON=ON` добавляет дополнительные targets (nanobind-модули), но **не изменяет основную C++ библиотеку** — ни её исходники, ни compile definitions, ни зависимости. Python bindings пристраиваются сбоку, линкуясь к уже собранной библиотеке.

Это означает, что при переключении `TERMIN_BUILD_PYTHON` с OFF на ON основная библиотека не пересобирается — cmake инкрементально добавляет только новые targets.

### Две стадии сборки

Сборка разделена на две стадии (C++ → bindings) не потому что они конфликтуют, а для практического удобства: если Python или nanobind не установлены, хотя бы C++ часть соберётся. Технически можно собирать всё сразу с `-DTERMIN_BUILD_PYTHON=ON` — результат будет идентичным.

Обе стадии используют один и тот же build directory (`build/Release`). Вторая стадия переконфигурирует cmake, но благодаря инкрементальности C++ часть не пересобирается.

### Структура модуля с биндингами

Биндинги строятся через [nanobind](https://github.com/wjakob/nanobind). Каждый модуль может опционально собирать Python-расширение при `-DTERMIN_BUILD_PYTHON=ON`.

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

---

## Компонентные библиотеки

Для однотипных компонентных модулей есть cmake-хелпер `TerminModule.cmake` с макросом `termin_add_module()`. Он автоматизирует создание shared library, настройку экспортов, RPATH и install-правил.

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
- [ ] Добавить в `modules.conf` в правильное место (порядок = порядок зависимостей)
