#ifndef TC_EVENT_H
#define TC_EVENT_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#include <tcbase/tcbase_api.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef const char* tc_event_type;

typedef struct tc_event {
    tc_event_type type;
    void* source;
    const void* payload;
    size_t payload_size;
    uint64_t flags;
} tc_event;

typedef struct tc_event_bus tc_event_bus;

typedef struct tc_event_subscription {
    uint64_t id;
} tc_event_subscription;

typedef void (*tc_event_handler_fn)(const tc_event* event, void* user_data);

TCBASE_API tc_event_bus* tc_event_bus_create(void);
TCBASE_API void tc_event_bus_destroy(tc_event_bus* bus);

TCBASE_API tc_event_subscription tc_event_bus_subscribe(
    tc_event_bus* bus,
    tc_event_type type,
    tc_event_handler_fn handler,
    void* user_data
);

TCBASE_API bool tc_event_bus_unsubscribe(tc_event_bus* bus, tc_event_subscription subscription);
TCBASE_API void tc_event_bus_publish(tc_event_bus* bus, const tc_event* event);

static inline bool tc_event_subscription_valid(tc_event_subscription subscription) {
    return subscription.id != 0;
}

#ifdef __cplusplus
}
#endif

#endif // TC_EVENT_H
