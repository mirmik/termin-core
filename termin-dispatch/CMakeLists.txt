cmake_minimum_required(VERSION 3.16)
project(termin_dispatch VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_BUILD_PYTHON "Build Python bindings" OFF)
option(TERMIN_DISPATCH_BUILD_TESTS "Build termin-dispatch tests" ON)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

add_library(termin_dispatch SHARED src/dispatcher.cpp)
add_library(termin_dispatch::termin_dispatch ALIAS termin_dispatch)

target_compile_definitions(termin_dispatch PRIVATE TERMIN_DISPATCH_EXPORTS)
target_include_directories(termin_dispatch
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)
target_link_libraries(termin_dispatch PRIVATE tcbase::termin_base)
termin_set_rpath_lib(termin_dispatch)

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

    nanobind_add_module(_dispatch_native NB_SHARED
        python/bindings/dispatch_module.cpp
    )
    target_link_libraries(_dispatch_native
        PRIVATE termin_dispatch tcbase::termin_base
    )
    termin_set_rpath_python(_dispatch_native)

    install(TARGETS _dispatch_native DESTINATION lib/python/termin/dispatch)
    install(DIRECTORY python/termin/dispatch/
        DESTINATION lib/python/termin/dispatch
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "lib" EXCLUDE
    )
endif()

if(TERMIN_DISPATCH_BUILD_TESTS)
    enable_testing()

    add_executable(termin_dispatch_c_test tests/test_dispatcher_c.c)
    target_link_libraries(termin_dispatch_c_test PRIVATE termin_dispatch)
    add_test(NAME termin_dispatch_c_test COMMAND termin_dispatch_c_test)

    find_package(Threads REQUIRED)
    add_executable(termin_dispatch_cpp_test tests/test_dispatcher_cpp.cpp)
    target_link_libraries(termin_dispatch_cpp_test
        PRIVATE termin_dispatch Threads::Threads
    )
    add_test(NAME termin_dispatch_cpp_test COMMAND termin_dispatch_cpp_test)
endif()

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

install(TARGETS termin_dispatch
    EXPORT termin_dispatchTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT termin_dispatchTargets
    FILE termin_dispatchTargets.cmake
    NAMESPACE termin_dispatch::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_dispatch
)

configure_package_config_file(
    cmake/termin_dispatchConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_dispatchConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_dispatch
)
write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_dispatchConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_dispatchConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_dispatchConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_dispatch
)

termin_label_tests_in_directory("termin-dispatch")
