#include <tcbase/tc_event.h>
#include <tcbase/tgfx_intern_string.h>
#include <stdlib.h>
#include <string.h>

typedef struct tc_event_subscription_record {
    uint64_t id;
    tc_event_type type;
    tc_event_handler_fn handler;
    void* user_data;
    bool active;
} tc_event_subscription_record;

struct tc_event_bus {
    tc_event_subscription_record* records;
    size_t count;
    size_t capacity;
    uint64_t next_id;
};

tc_event_bus* tc_event_bus_create(void) {
    tc_event_bus* bus = (tc_event_bus*)calloc(1, sizeof(tc_event_bus));
    if (!bus) return NULL;
    bus->next_id = 1;
    return bus;
}

void tc_event_bus_destroy(tc_event_bus* bus) {
    if (!bus) return;
    free(bus->records);
    free(bus);
}

static bool tc_event_bus_grow(tc_event_bus* bus) {
    size_t new_capacity = bus->capacity == 0 ? 8 : bus->capacity * 2;
    tc_event_subscription_record* new_records = (tc_event_subscription_record*)realloc(
        bus->records,
        new_capacity * sizeof(tc_event_subscription_record)
    );
    if (!new_records) return false;
    memset(new_records + bus->capacity, 0,
           (new_capacity - bus->capacity) * sizeof(tc_event_subscription_record));
    bus->records = new_records;
    bus->capacity = new_capacity;
    return true;
}

tc_event_subscription tc_event_bus_subscribe(
    tc_event_bus* bus,
    tc_event_type type,
    tc_event_handler_fn handler,
    void* user_data
) {
    tc_event_subscription invalid = {0};
    if (!bus || !type || !handler) return invalid;

    if (bus->count >= bus->capacity && !tc_event_bus_grow(bus)) {
        return invalid;
    }

    uint64_t id = bus->next_id++;
    if (id == 0) {
        id = bus->next_id++;
    }

    tc_event_subscription_record* record = &bus->records[bus->count++];
    record->id = id;
    record->type = tgfx_intern_string(type);
    record->handler = handler;
    record->user_data = user_data;
    record->active = true;

    return (tc_event_subscription){id};
}

bool tc_event_bus_unsubscribe(tc_event_bus* bus, tc_event_subscription subscription) {
    if (!bus || !tc_event_subscription_valid(subscription)) return false;

    for (size_t i = 0; i < bus->count; ++i) {
        tc_event_subscription_record* record = &bus->records[i];
        if (record->id == subscription.id && record->active) {
            record->active = false;
            record->handler = NULL;
            record->user_data = NULL;
            return true;
        }
    }

    return false;
}

void tc_event_bus_publish(tc_event_bus* bus, const tc_event* event) {
    if (!bus || !event || !event->type) return;

    tc_event_type type = tgfx_intern_string(event->type);
    for (size_t i = 0; i < bus->count; ++i) {
        tc_event_subscription_record* record = &bus->records[i];
        if (!record->active || !record->handler || record->type != type) {
            continue;
        }
        record->handler(event, record->user_data);
    }
}
