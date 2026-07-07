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

#endif // TCBASE_TYPES_API_H
