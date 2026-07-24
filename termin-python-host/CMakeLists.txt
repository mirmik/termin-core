cmake_minimum_required(VERSION 3.16)
project(termin_python_host VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(Python COMPONENTS Interpreter Development REQUIRED)

add_library(termin_python_host SHARED
    src/python_host.cpp
)
add_library(termin_python_host::termin_python_host ALIAS termin_python_host)

target_compile_definitions(termin_python_host PRIVATE
    TERMIN_PYTHON_HOST_EXPORTS
    TERMIN_PYTHON_EXPECTED_SOABI="${Python_SOABI}"
)
target_include_directories(termin_python_host
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)
target_link_libraries(termin_python_host PRIVATE Python::Python)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)
termin_set_rpath_lib(termin_python_host)
if(NOT WIN32)
    execute_process(
        COMMAND "${Python_EXECUTABLE}" -I -c
            "import sysconfig; print(sysconfig.get_config_var('LIBDIR') or '')"
        OUTPUT_VARIABLE _termin_python_library_dir
        OUTPUT_STRIP_TRAILING_WHITESPACE
        RESULT_VARIABLE _termin_python_library_dir_result
    )
    if(NOT _termin_python_library_dir_result EQUAL 0
       OR NOT IS_DIRECTORY "${_termin_python_library_dir}")
        message(FATAL_ERROR
            "Could not resolve the Python runtime library directory for "
            "${Python_EXECUTABLE}")
    endif()
    set_property(
        TARGET termin_python_host
        APPEND PROPERTY BUILD_RPATH "${_termin_python_library_dir}"
    )
    set_target_properties(termin_python_host PROPERTIES
        BUILD_WITH_INSTALL_RPATH FALSE
    )
endif()

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

install(TARGETS termin_python_host
    EXPORT termin_python_hostTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT termin_python_hostTargets
    FILE termin_python_hostTargets.cmake
    NAMESPACE termin_python_host::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_python_host
)

configure_package_config_file(
    cmake/termin_python_hostConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_python_hostConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_python_host
)
write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_python_hostConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_python_hostConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_python_hostConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_python_host
)
