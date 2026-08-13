cmake_minimum_required(VERSION 3.20)
project(termin_core_installed_consumers LANGUAGES CXX)

if(NOT DEFINED CORE_SDK_ROOT OR NOT IS_ABSOLUTE "${CORE_SDK_ROOT}")
    message(FATAL_ERROR "CORE_SDK_ROOT must name the absolute relocated Core SDK")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_FIND_PACKAGE_NO_PACKAGE_REGISTRY ON)
set(CMAKE_FIND_USE_PACKAGE_REGISTRY OFF)
set(CMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY OFF)

macro(find_core_package package_name)
    find_package(
        ${package_name} CONFIG REQUIRED
        PATHS "${CORE_SDK_ROOT}"
        NO_DEFAULT_PATH
    )
endmacro()

find_core_package(termin_base)
find_core_package(termin_dispatch)

find_package(
    Python 3.14 EXACT REQUIRED
    COMPONENTS Interpreter Development.Module Development.Embed
)
find_core_package(nanobind)
find_core_package(termin_inspect)
find_core_package(termin_python_host)

add_executable(core_native_consumer native_consumer.cpp)
target_link_libraries(
    core_native_consumer PRIVATE
    tcbase::termin_base
    termin_dispatch::termin_dispatch
    termin_inspect::termin_inspect
)

add_executable(core_python_host_consumer python_host_consumer.cpp)
target_link_libraries(
    core_python_host_consumer PRIVATE
    termin_python_host::termin_python_host
)

nanobind_add_module(core_fixture NB_SHARED extension.cpp)
target_link_libraries(
    core_fixture PRIVATE
    tcbase::termin_base
    termin_dispatch::termin_dispatch
    termin_inspect::termin_inspect
)
