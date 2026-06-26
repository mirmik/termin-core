#include <tcbase/tc_version.h>

const char* tc_version(void) {
    return TC_VERSION_STRING;
}

int tc_version_major(void) {
    return TC_VERSION_MAJOR;
}

int tc_version_minor(void) {
    return TC_VERSION_MINOR;
}

int tc_version_patch(void) {
    return TC_VERSION_PATCH;
}

int tc_version_int(void) {
    return TC_VERSION;
}
