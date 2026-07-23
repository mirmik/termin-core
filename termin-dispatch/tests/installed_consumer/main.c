#include "termin/dispatch/dispatcher.h"

#include <assert.h>

static tc_dispatch_callback_result increment(void* user_data) {
    ++*(int*)user_data;
    return TC_DISPATCH_CALLBACK_OK;
}

int main(void) {
    int value = 0;
    tc_dispatcher* dispatcher = tc_dispatcher_create();
    assert(dispatcher);
    assert(tc_dispatcher_post(
        dispatcher, increment, NULL, &value, NULL
    ));
    const tc_dispatch_stats stats =
        tc_dispatcher_drain(dispatcher, TC_DISPATCH_ALL);
    assert(stats.executed == 1);
    assert(value == 1);
    tc_dispatcher_destroy(dispatcher);
    return 0;
}
