// tcbase/types/api.h - shared C API export macro
#ifndef TCBASE_TYPES_API_H
#define TCBASE_TYPES_API_H

// Backward-compatible export macro used by existing C APIs.
// Each library that exposes TC_API symbols defines TC_EXPORTS when building.
#ifndef TC_API
    #ifdef _WIN32
        #ifdef TC_EXPORTS
            #define TC_API __declspec(dllexport)
        #else
            #define TC_API __declspec(dllimport)
        #endif
    #else
        #define TC_API
    #endif
#endif

/*
 * Header-only C helpers do not cross an ABI boundary, but MSVC still emits
 * C4190 when their C++ facade return type has constructors or methods.
 * Suppress that diagnostic only on declarations that remain static inline.
 * Real exported C functions must use TC_API and an explicitly portable ABI.
 */
#ifndef TC_C_STATIC_INLINE
    #if defined(_MSC_VER) && defined(__cplusplus)
        #define TC_C_STATIC_INLINE \
            __pragma(warning(suppress: 4190)) static inline
    #else
        #define TC_C_STATIC_INLINE static inline
    #endif
#endif

#endif // TCBASE_TYPES_API_H
