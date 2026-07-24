cmake_minimum_required(VERSION 3.16)
project(termin_nanobind_sdk VERSION 0.1.0 LANGUAGES CXX)

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

find_package(Python 3.10 COMPONENTS Interpreter Development.Module REQUIRED)

execute_process(
    COMMAND ${Python_EXECUTABLE} -c
            "import nanobind, pathlib; print(pathlib.Path(nanobind.__file__).resolve().parent)"
    OUTPUT_VARIABLE NANOBIND_PY_ROOT
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
file(TO_CMAKE_PATH "${NANOBIND_PY_ROOT}" NANOBIND_PY_ROOT)
if(NOT EXISTS "${NANOBIND_PY_ROOT}/cmake/nanobind-config.cmake")
    message(FATAL_ERROR "nanobind Python package was not found. Install it before configuring termin-nanobind-sdk.")
endif()

execute_process(
    COMMAND ${Python_EXECUTABLE} -c
        "import importlib.metadata; print(importlib.metadata.version('nanobind'))"
    OUTPUT_VARIABLE NANOBIND_VERSION
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
if(NOT NANOBIND_VERSION)
    set(NANOBIND_VERSION "0.0.0")
endif()

set(nanobind_DIR "${NANOBIND_PY_ROOT}/cmake")
find_package(nanobind CONFIG REQUIRED)

if(NB_FREE_THREADED)
    set(TERMIN_NANOBIND_RUNTIME_NAME "nanobind-ft")
    set(TERMIN_NANOBIND_PROFILE_FREE_THREADED 1)
else()
    set(TERMIN_NANOBIND_RUNTIME_NAME "nanobind")
    set(TERMIN_NANOBIND_PROFILE_FREE_THREADED 0)
endif()

nanobind_build_library("${TERMIN_NANOBIND_RUNTIME_NAME}")
set_target_properties("${TERMIN_NANOBIND_RUNTIME_NAME}" PROPERTIES
    EXCLUDE_FROM_ALL FALSE
    TERMIN_NANOBIND_PYTHON_SOABI "${Python_SOABI}"
    TERMIN_NANOBIND_FREE_THREADED "${TERMIN_NANOBIND_PROFILE_FREE_THREADED}"
    EXPORT_PROPERTIES
        "TERMIN_NANOBIND_PYTHON_SOABI;TERMIN_NANOBIND_FREE_THREADED"
)

set(_nanobind_build_includes "${NANOBIND_PY_ROOT}/include")
set(_nanobind_install_includes "${CMAKE_INSTALL_LIBDIR}/nanobind/include")
list(APPEND _nanobind_build_includes ${Python_INCLUDE_DIRS})
if(EXISTS "${NANOBIND_PY_ROOT}/ext/robin_map/include")
    list(APPEND _nanobind_build_includes "${NANOBIND_PY_ROOT}/ext/robin_map/include")
    list(APPEND _nanobind_install_includes "${CMAKE_INSTALL_LIBDIR}/nanobind/ext/robin_map/include")
endif()

set(_nanobind_interface_includes "")
foreach(_include_dir IN LISTS _nanobind_build_includes)
    list(APPEND _nanobind_interface_includes "$<BUILD_INTERFACE:${_include_dir}>")
endforeach()
foreach(_include_dir IN LISTS _nanobind_install_includes)
    list(APPEND _nanobind_interface_includes "$<INSTALL_INTERFACE:${_include_dir}>")
endforeach()

set_target_properties("${TERMIN_NANOBIND_RUNTIME_NAME}" PROPERTIES
    BUILD_WITH_INSTALL_RPATH TRUE
    INSTALL_RPATH "$ORIGIN"
    INTERFACE_INCLUDE_DIRECTORIES "${_nanobind_interface_includes}"
)

install(TARGETS "${TERMIN_NANOBIND_RUNTIME_NAME}"
    EXPORT terminNanobindTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
if(TERMIN_NANOBIND_PROFILE_FREE_THREADED)
    set(_termin_nanobind_obsolete_runtime "nanobind")
else()
    set(_termin_nanobind_obsolete_runtime "nanobind-ft")
endif()
install(CODE
    "file(REMOVE
        \"\${CMAKE_INSTALL_PREFIX}/${CMAKE_INSTALL_LIBDIR}/${CMAKE_SHARED_LIBRARY_PREFIX}${_termin_nanobind_obsolete_runtime}${CMAKE_SHARED_LIBRARY_SUFFIX}\"
        \"\${CMAKE_INSTALL_PREFIX}/${CMAKE_INSTALL_BINDIR}/${_termin_nanobind_obsolete_runtime}${CMAKE_SHARED_LIBRARY_SUFFIX}\"
        \"\${CMAKE_INSTALL_PREFIX}/${CMAKE_INSTALL_LIBDIR}/${_termin_nanobind_obsolete_runtime}${CMAKE_IMPORT_LIBRARY_SUFFIX}\"
    )"
)
install(EXPORT terminNanobindTargets
    NAMESPACE nanobind::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin-nanobind
)

# Install the termin_nanobind Python helper package (runtime.py + __init__.py)
# into sdk/lib/python/ so bundled-Python consumers (termin_launcher, embedded
# editor) can import termin_nanobind.runtime the same way pip-installed users
# do.
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin_nanobind/
    DESTINATION lib/python/termin_nanobind
    FILES_MATCHING PATTERN "*.py"
)

install(DIRECTORY "${NANOBIND_PY_ROOT}/cmake/"
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/nanobind/cmake
)
install(DIRECTORY "${NANOBIND_PY_ROOT}/include/"
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/nanobind/include
)
install(DIRECTORY "${NANOBIND_PY_ROOT}/src/"
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/nanobind/src
)
if(EXISTS "${NANOBIND_PY_ROOT}/ext")
    install(DIRECTORY "${NANOBIND_PY_ROOT}/ext/"
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/nanobind/ext
    )
endif()

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/cmake/nanobindConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/nanobindConfig.cmake
    @ONLY
)
install(FILES
    ${CMAKE_CURRENT_SOURCE_DIR}/cmake/TerminNanobindProfile.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/nanobind
    RENAME termin-nanobind-profile.cmake
)
configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/cmake/nanobindConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/nanobind-config.cmake
    @ONLY
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/nanobindConfigVersion.cmake
    VERSION ${NANOBIND_VERSION}
    COMPATIBILITY SameMajorVersion
)
write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/nanobind-config-version.cmake
    VERSION ${NANOBIND_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/nanobindConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/nanobind-config.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/nanobindConfigVersion.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/nanobind-config-version.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/nanobind
)
