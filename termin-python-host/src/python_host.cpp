#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "termin/python_host/python_host.hpp"

#include <sstream>
#include <stdexcept>
#include <string_view>

#ifndef TERMIN_PYTHON_EXPECTED_SOABI
#define TERMIN_PYTHON_EXPECTED_SOABI ""
#endif

namespace termin::python_host {

namespace {

class ConfigGuard {
public:
    explicit ConfigGuard(PyConfig& config)
        : config_(config) {}

    ~ConfigGuard() {
        PyConfig_Clear(&config_);
    }

    ConfigGuard(const ConfigGuard&) = delete;
    ConfigGuard& operator=(const ConfigGuard&) = delete;

private:
    PyConfig& config_;
};

InitResult status_result(
    const Config& config,
    std::string_view operation,
    PyStatus status
) {
    InitResult result;
    result.exit_requested = PyStatus_IsExit(status);
    result.exit_code = result.exit_requested ? status.exitcode : 1;
    result.error = config.host_name + ": " + std::string(operation) + " failed";
    if (status.err_msg != nullptr) {
        result.error += ": ";
        result.error += status.err_msg;
    }
    return result;
}

std::string python_string(PyObject* value, const char* field) {
    if (value == nullptr) {
        throw std::runtime_error(std::string("Python ABI query returned null for ") + field);
    }
    if (!PyUnicode_Check(value)) {
        throw std::runtime_error(std::string("Python ABI query returned non-string ") + field);
    }
    const char* text = PyUnicode_AsUTF8(value);
    if (text == nullptr) {
        throw std::runtime_error(std::string("Python ABI query could not decode ") + field);
    }
    return text;
}

RuntimeAbi query_runtime_abi() {
    RuntimeAbi identity;
    const std::string version = Py_GetVersion();
    const std::size_t separator = version.find('.');
    const std::size_t minor_end = version.find('.', separator + 1);
    if (separator == std::string::npos || minor_end == std::string::npos) {
        throw std::runtime_error("Py_GetVersion returned malformed version: " + version);
    }
    identity.version = version.substr(0, minor_end);

    PyObject* sysconfig = PyImport_ImportModule("sysconfig");
    if (sysconfig == nullptr) {
        throw std::runtime_error("cannot import sysconfig while validating Python ABI");
    }
    PyObject* get_config_var = PyObject_GetAttrString(sysconfig, "get_config_var");
    if (get_config_var == nullptr || !PyCallable_Check(get_config_var)) {
        Py_XDECREF(get_config_var);
        Py_DECREF(sysconfig);
        throw std::runtime_error("sysconfig.get_config_var is unavailable");
    }

    PyObject* soabi_value = PyObject_CallFunction(get_config_var, "s", "SOABI");
    try {
        identity.soabi = python_string(soabi_value, "SOABI");
    } catch (...) {
        Py_XDECREF(soabi_value);
        Py_DECREF(get_config_var);
        Py_DECREF(sysconfig);
        throw;
    }
    Py_DECREF(soabi_value);

    PyObject* gil_value = PyObject_CallFunction(
        get_config_var,
        "s",
        "Py_GIL_DISABLED"
    );
    if (gil_value == nullptr) {
        Py_DECREF(get_config_var);
        Py_DECREF(sysconfig);
        throw std::runtime_error("cannot query sysconfig Py_GIL_DISABLED");
    }
    const int free_threaded = PyObject_IsTrue(gil_value);
    Py_DECREF(gil_value);
    Py_DECREF(get_config_var);
    Py_DECREF(sysconfig);
    if (free_threaded < 0) {
        throw std::runtime_error("cannot interpret sysconfig Py_GIL_DISABLED");
    }
    identity.free_threaded = free_threaded != 0;
    return identity;
}

std::string fetch_python_error() {
    if (!PyErr_Occurred()) {
        return {};
    }
    PyObject* type = nullptr;
    PyObject* value = nullptr;
    PyObject* traceback = nullptr;
    PyErr_Fetch(&type, &value, &traceback);
    PyErr_NormalizeException(&type, &value, &traceback);
    std::string message;
    if (value != nullptr) {
        PyObject* rendered = PyObject_Str(value);
        if (rendered != nullptr) {
            const char* text = PyUnicode_AsUTF8(rendered);
            if (text != nullptr) {
                message = text;
            }
            Py_DECREF(rendered);
        }
    }
    Py_XDECREF(traceback);
    Py_XDECREF(value);
    Py_XDECREF(type);
    PyErr_Clear();
    return message;
}

InitResult validate_initialized_runtime(const Config& config) {
    try {
        const RuntimeAbi expected = expected_abi();
        const RuntimeAbi actual = query_runtime_abi();
        if (expected.version != actual.version
            || expected.soabi != actual.soabi
            || expected.free_threaded != actual.free_threaded) {
            return InitResult{
                .ok = false,
                .exit_requested = false,
                .exit_code = 1,
                .error = config.host_name + ": Python ABI mismatch: expected "
                    + expected.describe() + ", initialized " + actual.describe(),
            };
        }
    } catch (const std::exception& error) {
        const std::string python_error = fetch_python_error();
        return InitResult{
            .ok = false,
            .exit_requested = false,
            .exit_code = 1,
            .error = config.host_name + ": Python ABI validation failed: "
                + error.what()
                + (python_error.empty() ? "" : ": " + python_error),
        };
    }
    return InitResult{.ok = true, .exit_requested = false, .exit_code = 0};
}

} // namespace

std::string RuntimeAbi::describe() const {
    std::ostringstream output;
    output << version << "|" << soabi << "|free_threaded="
           << (free_threaded ? "true" : "false");
    return output.str();
}

RuntimeAbi expected_abi() {
    RuntimeAbi identity;
    identity.version = std::to_string(PY_MAJOR_VERSION)
        + "." + std::to_string(PY_MINOR_VERSION);
    identity.soabi = TERMIN_PYTHON_EXPECTED_SOABI;
#ifdef Py_GIL_DISABLED
    identity.free_threaded = true;
#else
    identity.free_threaded = false;
#endif
    return identity;
}

RuntimeAbi runtime_abi() {
    if (!Py_IsInitialized()) {
        throw std::runtime_error("Python is not initialized");
    }
    return query_runtime_abi();
}

InitResult initialize(const Config& config) {
    if (Py_IsInitialized()) {
        return validate_initialized_runtime(config);
    }

    PyConfig python_config;
    PyConfig_InitPythonConfig(&python_config);
    ConfigGuard guard(python_config);
    python_config.isolated = config.isolated ? 1 : 0;
    python_config.use_environment = config.use_environment ? 1 : 0;
    python_config.user_site_directory = config.user_site_directory ? 1 : 0;
    python_config.site_import = config.site_import ? 1 : 0;
    python_config.write_bytecode = config.write_bytecode ? 1 : 0;
    python_config.parse_argv = config.parse_argv ? 1 : 0;

    PyStatus status;
    if (!config.home.empty()) {
#ifdef _WIN32
        const std::wstring home = config.home.wstring();
        status = PyConfig_SetString(
            &python_config,
            &python_config.home,
            home.c_str()
        );
#else
        status = PyConfig_SetBytesString(
            &python_config,
            &python_config.home,
            config.home.string().c_str()
        );
#endif
        if (PyStatus_Exception(status)) {
            return status_result(config, "configuring Python home", status);
        }
    }

    std::vector<std::string> arguments = config.argv;
    if (arguments.empty()) {
        arguments.push_back(config.host_name);
    }
    status = PyConfig_SetBytesString(
        &python_config,
        &python_config.program_name,
        arguments.front().c_str()
    );
    if (PyStatus_Exception(status)) {
        return status_result(config, "configuring Python program name", status);
    }

    std::vector<char*> argv;
    argv.reserve(arguments.size());
    for (std::string& argument : arguments) {
        argv.push_back(argument.data());
    }
    status = PyConfig_SetBytesArgv(
        &python_config,
        static_cast<Py_ssize_t>(argv.size()),
        argv.data()
    );
    if (PyStatus_Exception(status)) {
        return status_result(config, "configuring Python arguments", status);
    }

    status = Py_InitializeFromConfig(&python_config);
    if (PyStatus_Exception(status)) {
        return status_result(config, "initializing Python", status);
    }

    InitResult result = validate_initialized_runtime(config);
    if (!result.ok) {
        const int finalize_result = Py_FinalizeEx();
        if (finalize_result != 0) {
            result.error += "; cleanup after ABI rejection also failed";
        }
    }
    return result;
}

int finalize() {
    if (!Py_IsInitialized()) {
        return 0;
    }
    return Py_FinalizeEx();
}

} // namespace termin::python_host
