#include <nanobind/nanobind.h>

#include <inspect/tc_runtime_type_registry.h>
#include <tcbase/tc_version.h>
#include <termin/dispatch/dispatcher.hpp>

namespace nb = nanobind;

NB_MODULE(core_fixture, module) {
    module.def("probe", [] {
        termin::Dispatcher dispatcher;
        int value = 0;
        if (!dispatcher.defer([&value] { value = 42; })) {
            throw std::runtime_error("termin-dispatch rejected a deferred callback");
        }
        const auto stats = dispatcher.drain();
        if (stats.executed != 1 || tc_runtime_type_registry_type_count() != 0) {
            throw std::runtime_error("installed Core native contract failed");
        }
        return nb::make_tuple(tc_version(), value);
    });
}
