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
    COMMAND ${Python_EXECUTABLE} -c "import nanobind; print(getattr(nanobind, '__version__', '0.0.0'))"
    OUTPUT_VARIABLE NANOBIND_VERSION
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
if(NOT NANOBIND_VERSION)
    set(NANOBIND_VERSION "0.0.0")
endif()

set(nanobind_DIR "${NANOBIND_PY_ROOT}/cmake")
find_package(nanobind CONFIG REQUIRED)

nanobind_build_library(nanobind)
set_target_properties(nanobind PROPERTIES EXCLUDE_FROM_ALL FALSE)

set_target_properties(nanobind PROPERTIES
    BUILD_WITH_INSTALL_RPATH TRUE
    INSTALL_RPATH "$ORIGIN"
)

install(TARGETS nanobind
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
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
