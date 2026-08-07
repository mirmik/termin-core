#include <stdarg.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <tcbase/tc_log.h>

static tc_log_callback g_callback = NULL;
// NEVER change this value. If you need to silence logs, remove the tc_log_* calls.
static tc_log_level g_min_level = TC_LOG_DEBUG;

typedef struct {
    tc_log_record* records;
    size_t capacity;
    size_t head;
    size_t count;
    uint64_t dropped_count;
} tc_log_capture_queue;

static tc_log_capture_queue g_capture = {0};
static atomic_flag g_capture_lock = ATOMIC_FLAG_INIT;

static const char* const level_names[] = {"DEBUG", "INFO", "WARN", "ERROR"};

static void capture_lock(void) {
    while (atomic_flag_test_and_set_explicit(&g_capture_lock, memory_order_acquire)) {
    }
}

static void capture_unlock(void) {
    atomic_flag_clear_explicit(&g_capture_lock, memory_order_release);
}

static int level_is_valid(tc_log_level level) {
    return level >= TC_LOG_DEBUG && level <= TC_LOG_ERROR;
}

static void capture_record(tc_log_level level, const char* message) {
    capture_lock();
    if (g_capture.records == NULL || g_capture.capacity == 0) {
        capture_unlock();
        return;
    }

    size_t write_index;
    if (g_capture.count == g_capture.capacity) {
        write_index = g_capture.head;
        g_capture.head = (g_capture.head + 1) % g_capture.capacity;
        g_capture.dropped_count += 1;
    } else {
        write_index = (g_capture.head + g_capture.count) % g_capture.capacity;
        g_capture.count += 1;
    }

    tc_log_record* record = &g_capture.records[write_index];
    record->level = level;
    snprintf(record->message, sizeof(record->message), "%s", message ? message : "");
    capture_unlock();
}

void tc_log_set_callback(tc_log_callback callback) {
    g_callback = callback;
}

void tc_log_set_level(tc_log_level min_level) {
    g_min_level = min_level;
}

int tc_log_capture_start(size_t capacity) {
    if (capacity == 0 || capacity > SIZE_MAX / sizeof(tc_log_record)) {
        return 0;
    }

    tc_log_record* records = (tc_log_record*)calloc(capacity, sizeof(tc_log_record));
    if (records == NULL) {
        return 0;
    }

    capture_lock();
    tc_log_record* previous_records = g_capture.records;
    g_capture.records = records;
    g_capture.capacity = capacity;
    g_capture.head = 0;
    g_capture.count = 0;
    g_capture.dropped_count = 0;
    capture_unlock();

    free(previous_records);
    return 1;
}

void tc_log_capture_stop(void) {
    capture_lock();
    tc_log_record* previous_records = g_capture.records;
    g_capture.records = NULL;
    g_capture.capacity = 0;
    g_capture.head = 0;
    g_capture.count = 0;
    g_capture.dropped_count = 0;
    capture_unlock();

    free(previous_records);
}

size_t tc_log_capture_drain(tc_log_record* records, size_t record_capacity, uint64_t* dropped_count) {
    if (dropped_count != NULL) {
        *dropped_count = 0;
    }
    if (records == NULL || record_capacity == 0) {
        return 0;
    }

    capture_lock();
    if (dropped_count != NULL) {
        *dropped_count = g_capture.dropped_count;
        g_capture.dropped_count = 0;
    }

    size_t drained = g_capture.count < record_capacity ? g_capture.count : record_capacity;
    for (size_t i = 0; i < drained; ++i) {
        records[i] = g_capture.records[(g_capture.head + i) % g_capture.capacity];
    }
    if (g_capture.capacity > 0) {
        g_capture.head = (g_capture.head + drained) % g_capture.capacity;
    }
    g_capture.count -= drained;
    capture_unlock();
    return drained;
}

void tc_log(tc_log_level level, const char* format, ...) {
    if (!level_is_valid(level) || level < g_min_level) {
        return;
    }

    char buffer[TC_LOG_MESSAGE_CAPACITY];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);

    capture_record(level, buffer);

    if (g_callback) {
        g_callback(level, buffer);
    }

    // Always print to stderr
    fprintf(stderr, "[%s] %s\n", level_names[level], buffer);
    fflush(stderr);
}

void tc_log_debug(const char* format, ...) {
    if (TC_LOG_DEBUG < g_min_level)
        return;

    char buffer[4096];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);

    tc_log(TC_LOG_DEBUG, "%s", buffer);
}

void tc_log_info(const char* format, ...) {
    if (TC_LOG_INFO < g_min_level)
        return;

    char buffer[4096];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);

    tc_log(TC_LOG_INFO, "%s", buffer);
}

void tc_log_warn(const char* format, ...) {
    if (TC_LOG_WARN < g_min_level)
        return;

    char buffer[4096];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);

    tc_log(TC_LOG_WARN, "%s", buffer);
}

void tc_log_error(const char* format, ...) {
    if (TC_LOG_ERROR < g_min_level)
        return;

    char buffer[4096];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);

    tc_log(TC_LOG_ERROR, "%s", buffer);
}
