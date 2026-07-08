cmake_minimum_required(VERSION 3.16)
project(termin_base VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
option(TERMIN_BASE_BUILD_TESTS "Build termin-base tests" ON)

# termin_base library (tc_log + trent + settings + tc_value_trent)
set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS ON)
add_library(termin_base SHARED
    src/tc_log.c
    src/tc_profiler.c
    src/tc_tensor.c
    src/tc_value.c
    src/tc_pool.c
    src/tc_event.c
    src/tc_resource_map.c
    src/tc_string.c
    src/tc_uuid.c
    src/tc_version.c
    src/trent/trent.cpp
    src/trent/trent_path.cpp
    src/trent/string_ext.cpp
    src/trent/json.cpp
    src/trent/yaml.cpp
    src/settings.cpp
    src/tc_value_trent.cpp
    src/orbit_camera.cpp
)
if(COMMAND termin_add_alias_if_missing)
    termin_add_alias_if_missing(tcbase::termin_base termin_base)
endif()

target_include_directories(termin_base PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include/tcbase/trent>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include/tcbase>
    $<INSTALL_INTERFACE:include>
    $<INSTALL_INTERFACE:include/tcbase/trent>
    $<INSTALL_INTERFACE:include/tcbase>
)

target_compile_definitions(termin_base PRIVATE TCBASE_EXPORTS TC_EXPORTS)

# Python bindings
option(TERMIN_BUILD_PYTHON "Build Python bindings" OFF)

if(TERMIN_BUILD_PYTHON)
    add_subdirectory(python)
endif()

if(TERMIN_BASE_BUILD_TESTS)
    enable_testing()

    add_executable(termin_base_value_test tests/test_tc_value.c)
    set_target_properties(termin_base_value_test PROPERTIES LINKER_LANGUAGE CXX)
    target_include_directories(termin_base_value_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_base_value_test PRIVATE termin_base)
    if(UNIX AND NOT APPLE)
        target_link_libraries(termin_base_value_test PRIVATE m)
    endif()

    add_test(NAME termin_base_value_test COMMAND termin_base_value_test)

    add_executable(termin_base_string_test tests/test_tc_string.c)
    set_target_properties(termin_base_string_test PROPERTIES LINKER_LANGUAGE CXX)
    target_include_directories(termin_base_string_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_base_string_test PRIVATE termin_base)
    add_test(NAME termin_base_string_test COMMAND termin_base_string_test)

    add_executable(termin_base_tensor_test tests/test_tc_tensor.c)
    set_target_properties(termin_base_tensor_test PROPERTIES LINKER_LANGUAGE CXX)
    target_include_directories(termin_base_tensor_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_base_tensor_test PRIVATE termin_base)
    add_test(NAME termin_base_tensor_test COMMAND termin_base_tensor_test)

    add_executable(termin_base_orbit_camera_test tests/test_orbit_camera.cpp)
    target_include_directories(termin_base_orbit_camera_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_base_orbit_camera_test PRIVATE termin_base)
    add_test(NAME termin_base_orbit_camera_test COMMAND termin_base_orbit_camera_test)

    add_executable(termin_base_geometry_test tests/test_geometry.cpp)
    target_include_directories(termin_base_geometry_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_base_geometry_test PRIVATE termin_base)
    add_test(NAME termin_base_geometry_test COMMAND termin_base_geometry_test)
endif()

# Install
include(GNUInstallDirs)

install(TARGETS termin_base
    EXPORT termin_baseTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

install(DIRECTORY include/tcbase
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(DIRECTORY include/termin
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(DIRECTORY include/geom
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(FILES
    include/tc_profiler.h
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

# CMake config for find_package
install(EXPORT termin_baseTargets
    FILE termin_baseTargets.cmake
    NAMESPACE tcbase::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_base
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    cmake/termin_baseConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_baseConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_base
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_baseConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_baseConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_baseConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_base
)
