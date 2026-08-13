cmake_minimum_required(VERSION 3.18)
project(termin_core VERSION 0.1.0 LANGUAGES C CXX)

include(CMakePackageConfigHelpers)

option(TERMIN_BUILD_PYTHON "Build Python/nanobind bindings" OFF)
option(TERMIN_BUILD_TESTS "Build Core native tests" OFF)
option(TERMIN_USE_CCACHE "Use ccache when available" ON)
option(TERMIN_ENABLE_UNITY_BUILD "Enable unity builds" OFF)
option(TERMIN_ENABLE_PCH "Enable precompiled headers" ON)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

if(TERMIN_USE_CCACHE AND NOT MSVC)
    find_program(TERMIN_CCACHE_PROGRAM ccache)
    if(TERMIN_CCACHE_PROGRAM)
        set(CMAKE_C_COMPILER_LAUNCHER "${TERMIN_CCACHE_PROGRAM}" CACHE STRING "" FORCE)
        set(CMAKE_CXX_COMPILER_LAUNCHER "${TERMIN_CCACHE_PROGRAM}" CACHE STRING "" FORCE)
    endif()
endif()

function(termin_enable_unity_build_for target)
    if(TERMIN_ENABLE_UNITY_BUILD AND TARGET "${target}")
        set_target_properties("${target}" PROPERTIES
            UNITY_BUILD ON
            UNITY_BUILD_BATCH_SIZE 8
        )
    endif()
endfunction()

function(termin_enable_pch_for target)
    if(TERMIN_ENABLE_PCH AND TARGET "${target}")
        get_target_property(_termin_target_type "${target}" TYPE)
        if(NOT MSVC OR NOT _termin_target_type STREQUAL "SHARED_LIBRARY")
            target_precompile_headers("${target}" PRIVATE
                "$<$<COMPILE_LANGUAGE:CXX>:${CMAKE_CURRENT_FUNCTION_LIST_DIR}/cmake/termin_cpp_pch.hpp>"
            )
        endif()
    endif()
endfunction()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(TerminDependencies)
include(TerminTestMetadata)

if(TERMIN_BUILD_TESTS)
    if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/termin-thirdparty/guard/guard_c.h"
       OR NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/termin-thirdparty/guard/guard_main.h")
        message(FATAL_ERROR
            "TERMIN_BUILD_TESTS=ON requires termin-thirdparty/guard")
    endif()
    enable_testing()
endif()

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")

set(TERMIN_BASE_BUILD_TESTS ${TERMIN_BUILD_TESTS} CACHE BOOL "" FORCE)
set(TERMIN_DISPATCH_BUILD_TESTS ${TERMIN_BUILD_TESTS} CACHE BOOL "" FORCE)
set(TI_BUILD_TESTS ${TERMIN_BUILD_TESTS} CACHE BOOL "" FORCE)
set(TI_BUILD_PYTHON_TESTS ${TERMIN_BUILD_PYTHON} CACHE BOOL "" FORCE)
set(TERMIN_CLI_PYTHON_ONLY ON CACHE BOOL "" FORCE)

if(TERMIN_BUILD_PYTHON)
    include(TerminPython)
    termin_require_canonical_python(Interpreter Development)
    execute_process(
        COMMAND "${Python_EXECUTABLE}" -c
            "import nanobind, pathlib; print(pathlib.Path(nanobind.__file__).resolve().parent / 'cmake')"
        OUTPUT_VARIABLE TERMIN_NANOBIND_CMAKE_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
        RESULT_VARIABLE TERMIN_NANOBIND_CMAKE_RESULT
    )
    if(NOT TERMIN_NANOBIND_CMAKE_RESULT EQUAL 0)
        message(FATAL_ERROR "nanobind is unavailable for ${Python_EXECUTABLE}")
    endif()
    file(TO_CMAKE_PATH "${TERMIN_NANOBIND_CMAKE_DIR}" TERMIN_NANOBIND_CMAKE_DIR)
    set(nanobind_DIR "${TERMIN_NANOBIND_CMAKE_DIR}" CACHE PATH "" FORCE)

    add_subdirectory(termin-nanobind-sdk)
    set(TERMIN_NANOBIND_RUNTIME_TARGET "nanobind-ft")
    include(termin-nanobind-sdk/cmake/TerminNanobindProfile.cmake)
    add_subdirectory(termin-python-host)
endif()

add_subdirectory(termin-base)
add_subdirectory(termin-dispatch)
add_subdirectory(termin-inspect)
add_subdirectory(termin-cli)

configure_package_config_file(
    cmake/terminConfig.cmake.in
    "${CMAKE_CURRENT_BINARY_DIR}/terminConfig.cmake"
    INSTALL_DESTINATION lib/cmake/termin
)
write_basic_package_version_file(
    "${CMAKE_CURRENT_BINARY_DIR}/terminConfigVersion.cmake"
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)
install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/terminConfig.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/terminConfigVersion.cmake"
    DESTINATION lib/cmake/termin
)
