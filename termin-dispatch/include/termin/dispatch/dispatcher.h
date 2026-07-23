#ifndef TERMIN_DISPATCH_DISPATCHER_H
#define TERMIN_DISPATCH_DISPATCHER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "termin/dispatch/api.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_dispatcher tc_dispatcher;

typedef struct tc_dispatch_ticket {
    uint32_t slot;
    uint32_t generation;
} tc_dispatch_ticket;

typedef enum tc_dispatch_callback_result {
    TC_DISPATCH_CALLBACK_OK = 0,
    TC_DISPATCH_CALLBACK_FAILED = 1
} tc_dispatch_callback_result;

typedef tc_dispatch_callback_result (*tc_dispatch_callback)(void* user_data);
typedef void (*tc_dispatch_dispose)(void* user_data);

typedef struct tc_dispatch_stats {
    size_t executed;
    size_t failed;
    size_t remaining;
    bool busy;
    bool internal_error;
} tc_dispatch_stats;

#define TC_DISPATCH_ALL ((size_t)-1)

TERMIN_DISPATCH_API tc_dispatch_ticket tc_dispatch_ticket_invalid(void);
TERMIN_DISPATCH_API bool tc_dispatch_ticket_is_valid(tc_dispatch_ticket ticket);

TERMIN_DISPATCH_API tc_dispatcher* tc_dispatcher_create(void);

/*
 * Enqueue one callback. The dispatcher takes ownership of user_data only when
 * this function returns true. dispose may be NULL; otherwise it is invoked
 * exactly once after execution, cancellation, discard, or dispatcher
 * destruction.
 */
TERMIN_DISPATCH_API bool tc_dispatcher_post(
    tc_dispatcher* dispatcher,
    tc_dispatch_callback callback,
    tc_dispatch_dispose dispose,
    void* user_data,
    tc_dispatch_ticket* out_ticket
);

/*
 * Cancel queued work. Returns false for stale, executing, completed, or
 * otherwise unknown tickets.
 */
TERMIN_DISPATCH_API bool tc_dispatcher_cancel(
    tc_dispatcher* dispatcher,
    tc_dispatch_ticket ticket
);

/*
 * Execute up to limit callbacks on the calling thread. TC_DISPATCH_ALL drains
 * the complete batch visible at the beginning of the call. Work posted while
 * callbacks execute is reserved for a later drain.
 *
 * Concurrent drain calls are serialized. A recursive drain from a callback
 * returns immediately with busy=true.
 */
TERMIN_DISPATCH_API tc_dispatch_stats tc_dispatcher_drain(
    tc_dispatcher* dispatcher,
    size_t limit
);

/* Reject future posts. Already queued work remains available to drain. */
TERMIN_DISPATCH_API bool tc_dispatcher_close(tc_dispatcher* dispatcher);

/* Discard all currently queued work and dispose its payloads. */
TERMIN_DISPATCH_API size_t tc_dispatcher_discard_pending(tc_dispatcher* dispatcher);

TERMIN_DISPATCH_API bool tc_dispatcher_is_open(const tc_dispatcher* dispatcher);
TERMIN_DISPATCH_API size_t tc_dispatcher_pending_count(const tc_dispatcher* dispatcher);

/*
 * Close, wait for an active drain, discard pending work, and destroy the
 * dispatcher. No other API call may race with destroy itself.
 */
TERMIN_DISPATCH_API void tc_dispatcher_destroy(tc_dispatcher* dispatcher);

#ifdef __cplusplus
}
#endif

#endif
