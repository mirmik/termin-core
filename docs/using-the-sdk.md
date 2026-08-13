# Жизнь за пределами checkout

Главный продукт этого репозитория — не build directory и не набор `.so` рядом
с исходниками. Главный продукт — установленный SDK, который не знает, где его
собрали.

Это позволяет нарезать Termin на доменные репозитории без старого фокуса:
«если package не найден, заглянем в соседнюю папку». Такой fallback удобен
ровно до первого CI runner, другой рабочей станции или двух веток, случайно
собранных вместе.

## CMake contract

Передайте корень SDK через `CMAKE_PREFIX_PATH` и находите только установленные
packages:

```cmake
find_package(termin_base CONFIG REQUIRED)
find_package(termin_dispatch CONFIG REQUIRED)
find_package(termin_inspect CONFIG REQUIRED)
find_package(termin_python_host CONFIG REQUIRED)
```

Основные targets:

| Package | Target |
| --- | --- |
| `termin_base` | `tcbase::termin_base` |
| `termin_dispatch` | `termin_dispatch::termin_dispatch` |
| `termin_inspect` | `termin_inspect::termin_inspect` |
| `termin_python_host` | `termin_python_host::termin_python_host` |

Package `termin` также предоставляет лёгкий aggregate target
`termin::termin`, но конкретные packages лучше выражают реальные зависимости.

## Python contract

Запускайте код через `sdk/bin/termin_python`. Launcher знает layout SDK и
изолирует процесс от случайного `PYTHONPATH`, user site и системных packages.

```console
/opt/termin-core/sdk/bin/termin_python -I tool.py
```

Внутри находятся wheels и установленные distributions:

- `tcbase`;
- `termin-dispatch`;
- `termin-inspect`;
- `termin-mcp`;
- `termin-nanobind`;
- build-time пакет `termin-build-tools`.

Нельзя взять native extension из одного SDK, интерпретатор из второго и
`libnanobind-ft` из третьего. Manifest и smoke-проверки существуют именно для
того, чтобы эта комбинация не получила шанс казаться рабочей.

## Identity вместо надежды

Host SDK содержит manifests с:

- продуктом и Python ABI;
- content-derived native build ID;
- перечнем и hashes native artifacts;
- происхождением wheels и runtime packages.

Android и Web SDK имеют отдельный `termin-core-platform.json`, где записаны
target system, architecture, toolchain и его версия. Web SDK для `wasm32` не
является урезанным host SDK; это другой артефакт с другой идентичностью.

## Проверка relocation

```console
task smoke
```

Проверка делает больше, чем `import tcbase` в родном checkout:

1. копирует SDK во временное место;
2. очищает переменные, через которые могли просочиться исходники;
3. проверяет отрицательный сценарий с отсутствующим CMake package;
4. собирает C++ executable, embedded-Python host и nanobind extension;
5. запускает их против перемещённого SDK;
6. сверяет manifests, hashes, wheels, ABI и import graph.

Иными словами, consumer получает не обещание переносимости, а регулярно
исполняемый протокол проверки.

## Что должен делать доменный репозиторий

Репозиторий Graphics, Physics или будущий Termin application layer должен:

- принимать явный путь к установленному Core SDK;
- использовать CMake packages и публичные headers;
- сверять platform identity для cross-компиляции;
- не добавлять sibling-checkout fallback;
- не копировать исходники Core в собственное дерево;
- запускать хотя бы один installed-consumer smoke в CI.

Это звучит строже, чем обычная локальная разработка. Зато граф зависимостей
остаётся правдой даже после того, как исходный монорепозиторий перестаёт быть
центром вселенной.
