if(NOT DEFINED TERMIN_NANOBIND_RUNTIME_TARGET)
    message(FATAL_ERROR
        "TERMIN_NANOBIND_RUNTIME_TARGET must name the canonical SDK runtime target")
endif()
if(NOT TARGET "${TERMIN_NANOBIND_RUNTIME_TARGET}")
    message(FATAL_ERROR
        "Canonical nanobind runtime target does not exist: "
        "${TERMIN_NANOBIND_RUNTIME_TARGET}")
endif()
get_target_property(
    _termin_nanobind_runtime_free_threaded
    "${TERMIN_NANOBIND_RUNTIME_TARGET}"
    TERMIN_NANOBIND_FREE_THREADED
)
if(_termin_nanobind_runtime_free_threaded STREQUAL
   "_termin_nanobind_runtime_free_threaded-NOTFOUND")
    message(FATAL_ERROR
        "Canonical nanobind runtime target has no ABI metadata: "
        "${TERMIN_NANOBIND_RUNTIME_TARGET}")
endif()
if(NOT "${_termin_nanobind_runtime_free_threaded}" STREQUAL "1")
    message(FATAL_ERROR
        "Canonical nanobind runtime target is not free-threaded: "
        "${TERMIN_NANOBIND_RUNTIME_TARGET}")
endif()

# Termin owns one shared nanobind runtime for the complete native extension
# graph. Consumers select NB_SHARED; the SDK always supplies the free-threaded
# CPython 3.14t implementation.
function(termin_nanobind_link_runtime target_name visibility)
    if(NOT TARGET "${target_name}")
        message(FATAL_ERROR
            "Cannot attach the nanobind ABI profile to missing target: "
            "${target_name}")
    endif()
    if(NOT visibility STREQUAL "PRIVATE"
       AND NOT visibility STREQUAL "PUBLIC"
       AND NOT visibility STREQUAL "INTERFACE")
        message(FATAL_ERROR
            "termin_nanobind_link_runtime(${target_name} ...) requires "
            "PRIVATE, PUBLIC, or INTERFACE visibility")
    endif()

    target_link_libraries(
        "${target_name}"
        "${visibility}" "${TERMIN_NANOBIND_RUNTIME_TARGET}"
    )
    target_compile_definitions(
        "${target_name}" "${visibility}" NB_FREE_THREADED
    )
    set_target_properties("${target_name}" PROPERTIES
        TERMIN_NANOBIND_PROFILE TRUE
        TERMIN_NANOBIND_FREE_THREADED 1
    )
endfunction()

function(nanobind_add_module name)
    cmake_parse_arguments(PARSE_ARGV 1 ARG
        "STABLE_ABI;FREE_THREADED;NB_STATIC;NB_SHARED;PROTECT_STACK;LTO;NOMINSIZE;NOSTRIP;MUSL_DYNAMIC_LIBCPP;NB_SUPPRESS_WARNINGS"
        "NB_DOMAIN" "")

    if(ARG_NB_STATIC OR NOT ARG_NB_SHARED OR ARG_STABLE_ABI OR ARG_NB_DOMAIN)
        message(FATAL_ERROR
            "termin-nanobind-sdk supports only canonical NB_SHARED modules. "
            "Use nanobind_add_module(${name} NB_SHARED ...); the SDK selects "
            "the Python threading ABI centrally.")
    endif()
    add_library(${name} MODULE ${ARG_UNPARSED_ARGUMENTS})
    nanobind_compile_options(${name})
    nanobind_link_options(${name})
    set_target_properties(${name} PROPERTIES
        LINKER_LANGUAGE CXX
        TERMIN_NANOBIND_PROFILE TRUE
        TERMIN_NANOBIND_FREE_THREADED 1
    )
    nanobind_extension(${name})

    target_link_libraries(${name} PRIVATE Python::Module)
    termin_nanobind_link_runtime(${name} PRIVATE)

    if(NOT ARG_PROTECT_STACK)
        nanobind_disable_stack_protector(${name})
    endif()
    if(NOT ARG_NOMINSIZE)
        nanobind_opt_size(${name})
    endif()
    if(NOT ARG_NOSTRIP)
        nanobind_strip(${name})
    endif()
    if(ARG_LTO)
        nanobind_lto(${name})
    endif()
    nanobind_set_visibility(${name})

    set_property(
        GLOBAL APPEND PROPERTY TERMIN_NANOBIND_MODULE_TARGETS "${name}"
    )
endfunction()
