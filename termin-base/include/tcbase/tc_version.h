// tc_version.h - Termin version info shared by native modules.
#ifndef TCBASE_TC_VERSION_H
#define TCBASE_TC_VERSION_H

#include <tcbase/tcbase_api.h>

#define TC_VERSION_MAJOR 0
#define TC_VERSION_MINOR 1
#define TC_VERSION_PATCH 10

#define TC_VERSION_XSTRING(s) TC_VERSION_STRINGIFY(s)
#define TC_VERSION_STRINGIFY(s) #s

#define TC_VERSION_STRING TC_VERSION_XSTRING(TC_VERSION_MAJOR) "." TC_VERSION_XSTRING(TC_VERSION_MINOR) "." TC_VERSION_XSTRING(TC_VERSION_PATCH)
#define TC_VERSION ((int)((TC_VERSION_MAJOR << 16) | (TC_VERSION_MINOR << 8) | (TC_VERSION_PATCH)))

#ifdef __cplusplus
extern "C" {
#endif

TCBASE_API const char* tc_version(void);
TCBASE_API int tc_version_major(void);
TCBASE_API int tc_version_minor(void);
TCBASE_API int tc_version_patch(void);
TCBASE_API int tc_version_int(void);

#ifdef __cplusplus
}
#endif

#endif // TCBASE_TC_VERSION_H
