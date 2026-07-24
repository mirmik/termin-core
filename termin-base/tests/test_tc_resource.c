#include "guard_c.h"
#include <tcbase/tc_resource.h>
#include <string.h>

typedef struct loader_probe {
    char observed_uuid[TC_UUID_SIZE];
    int calls;
    bool result;
} loader_probe;

static bool probe_loader(const char* uuid, void* user_data) {
    loader_probe* probe = (loader_probe*)user_data;
    probe->calls++;
    tc_resource_copy_uuid(
        probe->observed_uuid,
        sizeof(probe->observed_uuid),
        uuid,
        "probe_loader"
    );
    return probe->result;
}

int main(void) {
    loader_probe first = {{0}, 0, true};
    loader_probe second = {{0}, 0, true};

    tc_resource_clear_loader();
    GUARD_C_CHECK(!tc_resource_request_load("missing"));

    tc_resource_set_loader(probe_loader, &first);
    GUARD_C_CHECK(tc_resource_request_load("first"));
    GUARD_C_CHECK(first.calls == 1);
    GUARD_C_CHECK(strcmp(first.observed_uuid, "first") == 0);

    tc_resource_set_loader(probe_loader, &second);
    GUARD_C_CHECK(tc_resource_request_load("second"));
    GUARD_C_CHECK(first.calls == 1);
    GUARD_C_CHECK(second.calls == 1);
    GUARD_C_CHECK(strcmp(second.observed_uuid, "second") == 0);

    tc_resource_clear_loader();
    GUARD_C_CHECK(!tc_resource_request_load("second"));

    tc_resource_header header;
    loader_probe probe = {{0}, 0, false};
    tc_resource_header_init(&header, "lazy-resource");
    tc_resource_set_loader(probe_loader, &probe);

    GUARD_C_CHECK(!tc_resource_header_ensure_loaded(&header));
    GUARD_C_CHECK(header.is_loaded == 0);
    GUARD_C_CHECK(strcmp(probe.observed_uuid, "lazy-resource") == 0);

    probe.result = true;
    GUARD_C_CHECK(tc_resource_header_ensure_loaded(&header));
    GUARD_C_CHECK(header.is_loaded == 1);
    GUARD_C_CHECK(probe.calls == 2);

    GUARD_C_CHECK(tc_resource_header_ensure_loaded(&header));
    GUARD_C_CHECK(probe.calls == 2);

    tc_resource_clear_loader();
    return 0;
}
