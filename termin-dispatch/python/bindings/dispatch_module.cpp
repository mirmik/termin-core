#include "termin/dispatch/dispatcher.hpp"

#include "tcbase/tc_log.h"

#include <nanobind/nanobind.h>

#include <Python.h>

#include <cstddef>
#include <memory>
#include <stdexcept>

namespace nb = nanobind;
using namespace nb::literals;

namespace {

struct PythonCallback {
    explicit PythonCallback(PyObject* object) : object(object) {
        Py_INCREF(object);
    }

    PyObject* object;
};

tc_dispatch_callback_result invoke_python_callback(void* user_data) {
    auto* payload = static_cast<PythonCallback*>(user_data);
    const PyGILState_STATE gil = PyGILState_Ensure();
    PyObject* result = PyObject_CallNoArgs(payload->object);
    if (!result) {
        tc_log_error("[termin-dispatch/python] deferred callback failed");
        PyErr_Print();
        PyGILState_Release(gil);
        return TC_DISPATCH_CALLBACK_FAILED;
    }
    Py_DECREF(result);
    PyGILState_Release(gil);
    return TC_DISPATCH_CALLBACK_OK;
}

void dispose_python_callback(void* user_data) {
    auto* payload = static_cast<PythonCallback*>(user_data);
    if (Py_IsInitialized()) {
        const PyGILState_STATE gil = PyGILState_Ensure();
        Py_DECREF(payload->object);
        PyGILState_Release(gil);
    } else {
        tc_log_error(
            "[termin-dispatch/python] Python finalized before callback disposal"
        );
    }
    delete payload;
}

class PythonDispatcher {
public:
    termin::DeferredCall defer(nb::object callback) {
        if (!PyCallable_Check(callback.ptr())) {
            throw nb::type_error("callback must be callable");
        }

        std::unique_ptr<PythonCallback> payload(
            new PythonCallback(callback.ptr())
        );
        termin::DeferredCall call = dispatcher_.post(
            &invoke_python_callback,
            &dispose_python_callback,
            payload.get()
        );
        if (!call) {
            throw std::runtime_error("dispatcher is closed");
        }
        payload.release();
        return call;
    }

    tc_dispatch_stats run_pending(nb::object limit) {
        const size_t native_limit =
            limit.is_none() ? TC_DISPATCH_ALL : nb::cast<size_t>(limit);
        tc_dispatch_stats stats{};
        {
            nb::gil_scoped_release release;
            stats = dispatcher_.drain(native_limit);
        }
        return stats;
    }

    bool close() { return dispatcher_.close(); }
    size_t discard_pending() { return dispatcher_.discard_pending(); }
    bool is_open() const { return dispatcher_.is_open(); }
    size_t pending_count() const { return dispatcher_.pending_count(); }

private:
    termin::Dispatcher dispatcher_;
};

} // namespace

NB_MODULE(_dispatch_native, module) {
    module.doc() =
        "Caller-driven deferred dispatcher backed by the Termin C ABI";

    nb::class_<tc_dispatch_stats>(module, "DispatchStats")
        .def_ro("executed", &tc_dispatch_stats::executed)
        .def_ro("failed", &tc_dispatch_stats::failed)
        .def_ro("remaining", &tc_dispatch_stats::remaining)
        .def_ro("busy", &tc_dispatch_stats::busy)
        .def_ro("internal_error", &tc_dispatch_stats::internal_error);

    nb::class_<termin::DeferredCall>(module, "DeferredCall")
        .def("cancel", &termin::DeferredCall::cancel)
        .def_prop_ro(
            "valid",
            [](const termin::DeferredCall& call) {
                return static_cast<bool>(call);
            }
        );

    nb::class_<PythonDispatcher>(module, "Dispatcher")
        .def(nb::init<>())
        .def("defer", &PythonDispatcher::defer, "callback"_a)
        .def(
            "run_pending",
            &PythonDispatcher::run_pending,
            "limit"_a = nb::none()
        )
        .def("close", &PythonDispatcher::close)
        .def("discard_pending", &PythonDispatcher::discard_pending)
        .def_prop_ro("open", &PythonDispatcher::is_open)
        .def_prop_ro("pending_count", &PythonDispatcher::pending_count);
}
