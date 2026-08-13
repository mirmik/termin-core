#include <inspect/tc_runtime_type_registry.h>
#include <tcbase/tc_version.h>
#include <termin/dispatch/dispatcher.hpp>

#include <iostream>
#include <string_view>

int main() {
    if (std::string_view(tc_version()).empty()) {
        std::cerr << "tcbase returned an empty version\n";
        return 1;
    }

    termin::Dispatcher dispatcher;
    int value = 0;
    if (!dispatcher.defer([&value] { value = 42; })) {
        std::cerr << "termin-dispatch rejected a deferred callback\n";
        return 2;
    }
    const termin::DispatchStats stats = dispatcher.drain();
    if (stats.executed != 1 || value != 42) {
        std::cerr << "termin-dispatch did not execute the callback\n";
        return 3;
    }

    if (tc_runtime_type_registry_type_count() != 0) {
        std::cerr << "termin-inspect registry is not initially empty\n";
        return 4;
    }
    return 0;
}
