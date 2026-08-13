# Первый выезд

Никакого священного ритуала нет. Нужны Git, CMake, C/C++ toolchain, Python для
первичного запуска сборщика и [Task](https://taskfile.dev/). Целевой Python
система не выбирает на глаз: Core сам готовит закреплённый CPython 3.14t.

## Собрать SDK

```console
git clone https://github.com/mirmik/termin-core.git
cd termin-core
task build
```

На Windows команды те же. Task выберет PowerShell launcher; на Linux — shell
launcher. Результат появится в `sdk/`:

```text
sdk/
├── bin/termin_python        # termin_python.exe на Windows
├── include/                 # C, C++, Python и nanobind headers
├── lib/                     # библиотеки и CMake packages
├── wheels/                  # проверенный набор Python wheels
└── sdk-product.json         # установленный контракт продукта
```

Первый запуск может быть долгим: точный Python toolchain и runtime inputs
скачиваются и собираются один раз, затем переиспользуются.

## Посмотреть на Python

Используйте Python из SDK. Это не декоративная рекомендация: native-модули
собраны для конкретного free-threaded ABI.

```console
./sdk/bin/termin_python -I -c \
  "import tcbase, termin.dispatch, termin.inspect, termin.mcp; print('живы')"
```

На Windows:

```powershell
.\sdk\bin\termin_python.exe -I -c `
  "import tcbase, termin.dispatch, termin.inspect, termin.mcp; print('живы')"
```

Небольшой пример с dispatcher:

```python
from termin.dispatch import Dispatcher

dispatcher = Dispatcher()
dispatcher.defer(lambda: print("вызвано не сейчас, а когда мы решим"))

# Никакого скрытого потока: работу выполняет тот, кто вызвал run_pending().
stats = dispatcher.run_pending()
print(stats.executed)
```

Запустите файл через `sdk/bin/termin_python`. Системный Python может иметь
другую версию, другой SOABI и совершенно другие планы на вечер.

## Подключить C++

После установки Core предоставляет обычные CMake config packages:

```cmake
cmake_minimum_required(VERSION 3.20)
project(core_trip LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)

find_package(termin_base CONFIG REQUIRED)
find_package(termin_dispatch CONFIG REQUIRED)

add_executable(core_trip main.cpp)
target_link_libraries(core_trip PRIVATE
    tcbase::termin_base
    termin_dispatch::termin_dispatch
)
```

```cpp
#include <tcbase/tc_version.h>
#include <termin/dispatch/dispatcher.hpp>

#include <iostream>

int main() {
    termin::Dispatcher dispatcher;
    dispatcher.defer([] { std::cout << "работа выполнена\n"; });
    dispatcher.drain();
    std::cout << "Core " << tc_version() << '\n';
}
```

Сборка consumer-а:

```console
cmake -S . -B build -DCMAKE_PREFIX_PATH=/absolute/path/to/termin-core/sdk
cmake --build build
```

Core сознательно не поддерживает поиск соседнего checkout. Если CMake не
находит установленный package, это ошибка поставки SDK, а не приглашение
дотянуть исходники из случайного каталога.

## Проверить весь контракт

Для тестов нужен один test-only submodule:

```console
git submodule update --init termin-thirdparty/guard
task test
```

Для более короткой проверки уже собранного SDK:

```console
task smoke
```

В начале installed smoke можно увидеть намеренную CMake-ошибку о пропавшем
`termin_dispatch`. Проверка на минуту прячет package и убеждается, что consumer
не найдёт обходной путь. Затем package возвращается, и начинается настоящая
сборка.

## Android и Web

Это отдельные native-only SDK: в них нет host Python и wheels.

```console
task build:android -- --ndk /absolute/path/to/android-ndk
task build:web
```

Web-команда при необходимости сама установит закреплённый Emscripten в общий
versioned cache. Несколько репозиториев Termin с одной версией toolchain
используют одну копию.
