cmake_minimum_required(VERSION 3.16)
project(termin_cli LANGUAGES CXX)

include(GNUInstallDirs)
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../cmake")
include(TerminRpath)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(MSVC)
    set(OPTIMIZE_FLAGS /O2 /fp:precise)
else()
    set(OPTIMIZE_FLAGS -O3)
endif()

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()

function(termin_cli_add_tool target)
    add_executable(${target} ${ARGN})
    target_compile_features(${target} PRIVATE cxx_std_20)
    target_include_directories(${target} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_compile_options(${target} PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
    set_target_properties(${target} PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
    )
    termin_set_rpath_tool(${target})
    install(TARGETS ${target} RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
endfunction()

add_library(termin_cli_python_backend STATIC src/termin_python_backend.cpp)
target_include_directories(termin_cli_python_backend PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)

termin_cli_add_tool(termin src/termin.cpp)
termin_cli_add_tool(termin_modules_cli src/termin_modules_cli.cpp)
target_link_libraries(termin_modules_cli PRIVATE termin_cli_python_backend)
termin_cli_add_tool(termin_stdlib src/termin_stdlib.cpp)

if(TERMIN_BUILD_PYTHON)
    if(NOT TARGET termin_python_host::termin_python_host)
        find_package(termin_python_host REQUIRED)
    endif()
    termin_cli_add_tool(termin_python src/termin_python.cpp)
    target_link_libraries(termin_python PRIVATE termin_cli_python_backend)
    target_link_libraries(
        termin_python
        PRIVATE
            Python::Python
            termin_python_host::termin_python_host
    )
endif()

termin_cli_add_tool(termin_builder src/termin_builder.cpp)
target_link_libraries(termin_builder PRIVATE termin_cli_python_backend)

termin_cli_add_tool(termin_runner src/termin_runner.cpp)
target_link_libraries(termin_runner PRIVATE tcbase::termin_base termin_cli_python_backend)
