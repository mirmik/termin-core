cmake_minimum_required(VERSION 3.16)
project(termin_dispatch_installed_consumer LANGUAGES C CXX)

find_package(termin_dispatch CONFIG REQUIRED)

add_executable(termin_dispatch_installed_c main.c)
target_link_libraries(
    termin_dispatch_installed_c PRIVATE termin_dispatch::termin_dispatch
)

add_executable(termin_dispatch_installed_cpp main.cpp)
target_compile_features(termin_dispatch_installed_cpp PRIVATE cxx_std_20)
target_link_libraries(
    termin_dispatch_installed_cpp PRIVATE termin_dispatch::termin_dispatch
)
