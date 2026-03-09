cmake_minimum_required(VERSION 3.14)
project(termin_inspect C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(TI_BUILD_SHARED "Build shared library" ON)
option(TI_BUILD_TESTS "Build tests" ON)
option(TI_BUILD_CPP "Build C++ inspect/kind core runtime" ON)
option(TERMIN_BUILD_PYTHON "Build Python/nanobind inspect bridge" OFF)

set(TI_SOURCES
    src/tc_inspect.c
    src/tc_kind.c
)

set(TI_CPP_SOURCES)
if(TI_BUILD_CPP)
    list(APPEND TI_CPP_SOURCES
        src/tc_inspect_core_instance.cpp
        src/tc_kind_cpp.cpp
    )
endif()

set(TI_PY_SOURCES
    src/tc_kind_python_instance.cpp
    src/tc_inspect_python.cpp
)

set(TI_CORE_HEADERS
    include/tc_types.h
    include/tc_value.h
    include/tc_inspect_cpp.hpp
    include/inspect/tc_inspect.h
    include/inspect/tc_kind.h
    include/inspect/tc_kind_cpp.hpp
)

set(TI_PY_HEADERS
    include/inspect/tc_kind_python.hpp
    include/inspect/tc_inspect_python.hpp
)

find_package(termin_base REQUIRED)

if(TERMIN_BUILD_PYTHON)
    if(NOT Python_EXECUTABLE)
        if(WIN32)
            set(Python_EXECUTABLE "python")
        else()
            set(Python_EXECUTABLE "python3")
        endif()
    endif()

    find_package(Python 3.8 COMPONENTS Interpreter Development REQUIRED)

    find_package(nanobind CONFIG REQUIRED)
endif()

if(TI_BUILD_SHARED)
    add_library(termin_inspect SHARED ${TI_SOURCES} ${TI_CPP_SOURCES} ${TI_CORE_HEADERS})
    target_compile_definitions(termin_inspect PRIVATE TC_EXPORTS TERMIN_INSPECT_CPP_EXPORTS)
else()
    add_library(termin_inspect STATIC ${TI_SOURCES} ${TI_CPP_SOURCES} ${TI_CORE_HEADERS})
    target_compile_definitions(termin_inspect PRIVATE TERMIN_INSPECT_CPP_EXPORTS)
endif()

add_library(termin_inspect::termin_inspect ALIAS termin_inspect)

set_target_properties(termin_inspect PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    EXPORT_NAME termin_inspect
)

target_include_directories(termin_inspect
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)
target_link_libraries(termin_inspect PUBLIC tcbase::termin_base)

if(TERMIN_BUILD_PYTHON)
    if(TI_BUILD_SHARED)
        add_library(termin_inspect_python SHARED ${TI_PY_SOURCES} ${TI_PY_HEADERS})
        target_compile_definitions(termin_inspect_python PRIVATE TC_EXPORTS TERMIN_INSPECT_PYTHON_EXPORTS)
    else()
        add_library(termin_inspect_python STATIC ${TI_PY_SOURCES} ${TI_PY_HEADERS})
        target_compile_definitions(termin_inspect_python PRIVATE TERMIN_INSPECT_PYTHON_EXPORTS)
    endif()

    add_library(termin_inspect::termin_inspect_python ALIAS termin_inspect_python)
    add_library(termin_inspect::termin_inspect_binding ALIAS termin_inspect_python)

    set_target_properties(termin_inspect_python PROPERTIES
        POSITION_INDEPENDENT_CODE ON
        LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
        ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
        EXPORT_NAME termin_inspect_python
    )

    target_include_directories(termin_inspect_python
        PUBLIC
            $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
            $<INSTALL_INTERFACE:include>
        PRIVATE
            ${NB_DIR}/include
    )

    target_link_libraries(termin_inspect_python
        PUBLIC
            termin_inspect
        PRIVATE
            nanobind
            Python::Python
    )
endif()

if(WIN32)
    target_compile_definitions(termin_inspect PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()

if(MSVC)
    target_compile_options(termin_inspect PRIVATE /W3)
else()
    target_compile_options(termin_inspect PRIVATE -Wall -Wextra -Wno-stringop-truncation)
endif()

# _inspect_native Python module (InspectRegistry, Kind system)
if(TERMIN_BUILD_PYTHON AND nanobind_FOUND)
    nanobind_add_module(_inspect_native NB_SHARED
        python/bindings/inspect_module.cpp
    )
    target_link_libraries(_inspect_native PRIVATE termin_inspect_python)

    set(TI_PY_RPATH "$ORIGIN;$ORIGIN/..;$ORIGIN/../..;$ORIGIN/../../..")
    set_target_properties(_inspect_native PROPERTIES
        INSTALL_RPATH "${TI_PY_RPATH}"
        BUILD_WITH_INSTALL_RPATH TRUE
    )

    if(TI_PYTHON_PREFIX)
        install(TARGETS _inspect_native DESTINATION ${TI_PYTHON_PREFIX}/inspect)
    else()
        install(TARGETS _inspect_native DESTINATION lib/python/termin/inspect)
    endif()
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/inspect/
        DESTINATION lib/python/termin/inspect
        FILES_MATCHING PATTERN "*.py"
    )
endif()

if(TI_BUILD_TESTS)
    enable_testing()
    add_executable(termin_inspect_c_test tests/test_main.c)
    target_link_libraries(termin_inspect_c_test PRIVATE termin_inspect)
    add_test(NAME termin_inspect_c_test COMMAND termin_inspect_c_test)
    set_target_properties(termin_inspect_c_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )

    add_executable(termin_inspect_cpp_test tests/test_cpp_inspect.cpp)
    target_link_libraries(termin_inspect_cpp_test PRIVATE termin_inspect)
    add_test(NAME termin_inspect_cpp_test COMMAND termin_inspect_cpp_test)
    set_target_properties(termin_inspect_cpp_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )

    if(TERMIN_BUILD_PYTHON)
        add_executable(termin_inspect_python_test tests/test_python_inspect.cpp)
        target_link_libraries(termin_inspect_python_test PRIVATE termin_inspect_python Python::Python nanobind)
        target_include_directories(termin_inspect_python_test PRIVATE ${NB_DIR}/include)
        add_test(NAME termin_inspect_python_test COMMAND termin_inspect_python_test)
        set_target_properties(termin_inspect_python_test PROPERTIES
            RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
        )
    endif()
endif()

include(CMakePackageConfigHelpers)

write_basic_package_version_file(
    "${CMAKE_CURRENT_BINARY_DIR}/termin_inspectConfigVersion.cmake"
    VERSION 0.1.0
    COMPATIBILITY SameMajorVersion
)

configure_package_config_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/termin_inspectConfig.cmake.in"
    "${CMAKE_CURRENT_BINARY_DIR}/termin_inspectConfig.cmake"
    INSTALL_DESTINATION lib/cmake/termin_inspect
)

install(TARGETS termin_inspect
    EXPORT termin_inspectTargets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

if(TERMIN_BUILD_PYTHON)
    install(TARGETS termin_inspect_python
        EXPORT termin_inspectTargets
        LIBRARY DESTINATION lib
        ARCHIVE DESTINATION lib
        RUNTIME DESTINATION bin
    )
endif()


install(DIRECTORY include/ DESTINATION include)

install(EXPORT termin_inspectTargets
    FILE termin_inspectTargets.cmake
    NAMESPACE termin_inspect::
    DESTINATION lib/cmake/termin_inspect
)

install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/termin_inspectConfig.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/termin_inspectConfigVersion.cmake"
    DESTINATION lib/cmake/termin_inspect
)
