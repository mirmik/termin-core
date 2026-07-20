// tc_uuid.h - UUID and runtime id utilities.
#ifndef TCBASE_TC_UUID_H
#define TCBASE_TC_UUID_H

#include <stdint.h>

#include <tcbase/tcbase_api.h>

/* Canonical identifiers include readable engine and catalog names. */
#define TC_UUID_SIZE 64

#ifdef __cplusplus
extern "C" {
#endif

TCBASE_API void tc_generate_uuid(char* out);
TCBASE_API uint64_t tc_compute_runtime_id(const char* uuid);

#ifdef __cplusplus
}
#endif

#endif // TCBASE_TC_UUID_H
