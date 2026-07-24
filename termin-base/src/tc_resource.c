#include <tcbase/tc_resource.h>

static tc_resource_loader_fn g_resource_loader = NULL;
static void* g_resource_loader_user_data = NULL;

void tc_resource_set_loader(
    tc_resource_loader_fn callback,
    void* user_data
) {
    g_resource_loader = callback;
    g_resource_loader_user_data = callback ? user_data : NULL;
}

void tc_resource_clear_loader(void) {
    g_resource_loader = NULL;
    g_resource_loader_user_data = NULL;
}

bool tc_resource_request_load(const char* uuid) {
    if (!uuid || uuid[0] == '\0') {
        tc_log_error("tc_resource_request_load: resource UUID is empty");
        return false;
    }
    if (!g_resource_loader) {
        tc_log_warn(
            "tc_resource_request_load: no process resource loader is installed for '%s'",
            uuid
        );
        return false;
    }
    if (!g_resource_loader(uuid, g_resource_loader_user_data)) {
        tc_log_error(
            "tc_resource_request_load: process resource loader failed for '%s'",
            uuid
        );
        return false;
    }
    return true;
}
