#pragma once

#include <filesystem>
#include <string>
#include <vector>

#ifdef _WIN32
    #ifdef TERMIN_PYTHON_HOST_EXPORTS
        #define TERMIN_PYTHON_HOST_API __declspec(dllexport)
    #else
        #define TERMIN_PYTHON_HOST_API __declspec(dllimport)
    #endif
#else
    #define TERMIN_PYTHON_HOST_API __attribute__((visibility("default")))
#endif

namespace termin::python_host {

struct Config {
    std::string host_name = "Termin";
    std::filesystem::path home;
    std::vector<std::string> argv;
    bool isolated = true;
    bool use_environment = false;
    bool user_site_directory = false;
    bool site_import = true;
    bool write_bytecode = false;
    bool parse_argv = false;
};

struct InitResult {
    bool ok = false;
    bool exit_requested = false;
    int exit_code = 1;
    std::string error;
};

struct RuntimeAbi {
    std::string version;
    std::string soabi;
    bool free_threaded = false;

    std::string describe() const;
};

TERMIN_PYTHON_HOST_API InitResult initialize(const Config& config);
TERMIN_PYTHON_HOST_API int finalize();
TERMIN_PYTHON_HOST_API RuntimeAbi expected_abi();
TERMIN_PYTHON_HOST_API RuntimeAbi runtime_abi();

} // namespace termin::python_host
