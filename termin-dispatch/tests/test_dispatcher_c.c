#include "termin/dispatch/dispatcher.h"

#include <assert.h>
#include <stdlib.h>

typedef struct test_payload {
    tc_dispatcher* dispatcher;
    int* value;
    int increment;
    int* dispose_count;
    bool post_nested;
    bool recurse;
} test_payload;

static void dispose_payload(void* user_data) {
    test_payload* payload = (test_payload*)user_data;
    ++*payload->dispose_count;
    free(payload);
}

static tc_dispatch_callback_result add_value(void* user_data) {
    test_payload* payload = (test_payload*)user_data;
    *payload->value += payload->increment;

    if (payload->post_nested) {
        test_payload* nested = (test_payload*)calloc(1, sizeof(test_payload));
        assert(nested);
        nested->value = payload->value;
        nested->increment = 100;
        nested->dispose_count = payload->dispose_count;
        assert(tc_dispatcher_post(
            payload->dispatcher,
            add_value,
            dispose_payload,
            nested,
            NULL
        ));
    }

    if (payload->recurse) {
        const tc_dispatch_stats recursive =
            tc_dispatcher_drain(payload->dispatcher, TC_DISPATCH_ALL);
        assert(recursive.busy);
        assert(recursive.executed == 0);
    }
    return TC_DISPATCH_CALLBACK_OK;
}

static tc_dispatch_callback_result fail_callback(void* user_data) {
    (void)user_data;
    return TC_DISPATCH_CALLBACK_FAILED;
}

static test_payload* make_payload(
    tc_dispatcher* dispatcher,
    int* value,
    int increment,
    int* dispose_count
) {
    test_payload* payload = (test_payload*)calloc(1, sizeof(test_payload));
    assert(payload);
    payload->dispatcher = dispatcher;
    payload->value = value;
    payload->increment = increment;
    payload->dispose_count = dispose_count;
    return payload;
}

int main(void) {
    tc_dispatcher* dispatcher = tc_dispatcher_create();
    assert(dispatcher);

    int value = 0;
    int dispose_count = 0;
    tc_dispatch_ticket first = tc_dispatch_ticket_invalid();
    tc_dispatch_ticket second = tc_dispatch_ticket_invalid();
    assert(tc_dispatcher_post(
        dispatcher,
        add_value,
        dispose_payload,
        make_payload(dispatcher, &value, 1, &dispose_count),
        &first
    ));
    assert(tc_dispatcher_post(
        dispatcher,
        add_value,
        dispose_payload,
        make_payload(dispatcher, &value, 10, &dispose_count),
        &second
    ));

    tc_dispatch_stats stats = tc_dispatcher_drain(dispatcher, 1);
    assert(stats.executed == 1);
    assert(stats.failed == 0);
    assert(stats.remaining == 1);
    assert(value == 1);
    assert(dispose_count == 1);
    assert(!tc_dispatcher_cancel(dispatcher, first));
    assert(tc_dispatcher_cancel(dispatcher, second));
    assert(dispose_count == 2);

    test_payload* nesting =
        make_payload(dispatcher, &value, 5, &dispose_count);
    nesting->post_nested = true;
    nesting->recurse = true;
    assert(tc_dispatcher_post(
        dispatcher, add_value, dispose_payload, nesting, NULL
    ));
    stats = tc_dispatcher_drain(dispatcher, TC_DISPATCH_ALL);
    assert(stats.executed == 1);
    assert(stats.remaining == 1);
    assert(value == 6);
    stats = tc_dispatcher_drain(dispatcher, TC_DISPATCH_ALL);
    assert(stats.executed == 1);
    assert(stats.remaining == 0);
    assert(value == 106);

    assert(tc_dispatcher_post(
        dispatcher,
        fail_callback,
        NULL,
        NULL,
        NULL
    ));
    stats = tc_dispatcher_drain(dispatcher, TC_DISPATCH_ALL);
    assert(stats.executed == 1);
    assert(stats.failed == 1);

    test_payload* discarded =
        make_payload(dispatcher, &value, 1000, &dispose_count);
    assert(tc_dispatcher_post(
        dispatcher, add_value, dispose_payload, discarded, NULL
    ));
    assert(tc_dispatcher_discard_pending(dispatcher) == 1);
    assert(value == 106);
    assert(dispose_count == 5);

    assert(tc_dispatcher_close(dispatcher));
    assert(!tc_dispatcher_close(dispatcher));
    assert(!tc_dispatcher_is_open(dispatcher));
    test_payload* rejected =
        make_payload(dispatcher, &value, 1, &dispose_count);
    assert(!tc_dispatcher_post(
        dispatcher, add_value, dispose_payload, rejected, NULL
    ));
    dispose_payload(rejected);
    assert(dispose_count == 6);

    tc_dispatcher_destroy(dispatcher);
    return 0;
}
