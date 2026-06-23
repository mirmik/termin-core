#pragma once

#include <inspect/tc_inspect.h>

#ifdef __cplusplus
extern "C" {
#endif

#ifdef _WIN32
    #ifdef TERMIN_INSPECT_CPP_EXPORTS
        #define TC_INSPECT_INIT_API __declspec(dllexport)
    #else
        #define TC_INSPECT_INIT_API __declspec(dllimport)
    #endif
#else
    #define TC_INSPECT_INIT_API __attribute__((visibility("default")))
#endif

TC_INSPECT_INIT_API void tc_inspect_kind_core_init(void);
TC_INSPECT_INIT_API void tc_inspect_python_adapter_init(void);
TC_INSPECT_INIT_API void tc_inspect_core_init(void);

#ifdef __cplusplus
}
#endif
