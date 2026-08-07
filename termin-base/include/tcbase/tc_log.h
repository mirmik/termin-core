#ifndef TC_LOG_H
#define TC_LOG_H

// Shared logging system for all termin libraries.

#include "tcbase_api.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    TC_LOG_DEBUG = 0,
    TC_LOG_INFO = 1,
    TC_LOG_WARN = 2,
    TC_LOG_ERROR = 3
} tc_log_level;

// Callback for log interception (e.g. for editor console)
typedef void (*tc_log_callback)(tc_log_level level, const char* message);

enum {
    TC_LOG_MESSAGE_CAPACITY = 4096
};

typedef struct {
    tc_log_level level;
    char message[TC_LOG_MESSAGE_CAPACITY];
} tc_log_record;

// Set callback for log interception
TCBASE_API void tc_log_set_callback(tc_log_callback callback);

// Set minimum log level
TCBASE_API void tc_log_set_level(tc_log_level min_level);

// Start a process-wide bounded capture queue. Starting again replaces and
// clears the previous queue. Producers may log from any thread; consumers pull
// complete records without invoking callbacks on producer threads.
TCBASE_API int tc_log_capture_start(size_t capacity);

// Stop capture and discard all queued records. stderr and the optional callback
// remain active.
TCBASE_API void tc_log_capture_stop(void);

// Drain up to record_capacity oldest records. The returned dropped count covers
// records evicted by overflow since the previous drain.
TCBASE_API size_t tc_log_capture_drain(tc_log_record* records, size_t record_capacity, uint64_t* dropped_count);

// Log with specified level (printf-style)
TCBASE_API void tc_log(tc_log_level level, const char* format, ...);

TCBASE_API void tc_log_debug(const char* format, ...);
TCBASE_API void tc_log_info(const char* format, ...);
TCBASE_API void tc_log_warn(const char* format, ...);
TCBASE_API void tc_log_error(const char* format, ...);

#ifdef __cplusplus
}
#endif

#endif // TC_LOG_H
