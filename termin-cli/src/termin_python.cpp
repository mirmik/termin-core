#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "termin_python_backend.hpp"

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

namespace fs = std::filesystem;

struct PythonLayout {
    fs::path sdk_root;
    fs::path python_home;
    fs::path stdlib;
    fs::path site_packages;
};

struct LauncherOptions {
    bool print_info = false;
    std::optional<fs::path> overlay_manifest;
    std::vector<fs::path> extra_sites;
    std::vector<std::string> python_args;
};

std::optional<fs::path> find_linux_stdlib(const fs::path& sdk_root) {
    const fs::path lib_dir = sdk_root / "lib";
    std::error_code ec;
    if (!fs::is_directory(lib_dir, ec)) {
        return std::nullopt;
    }

    std::vector<fs::path> candidates;
    for (const fs::directory_entry& entry : fs::directory_iterator(lib_dir, ec)) {
        if (ec || !entry.is_directory(ec)) {
            continue;
        }
        const std::string name = entry.path().filename().string();
        if (name.rfind("python3.", 0) == 0 && fs::is_regular_file(entry.path() / "os.py", ec)) {
            candidates.push_back(entry.path());
        }
    }
    if (candidates.empty()) {
        return std::nullopt;
    }
    std::sort(candidates.begin(), candidates.end());
    return candidates.back();
}

PythonLayout resolve_layout() {
    PythonLayout layout;
    layout.sdk_root = termin_cli::python_backend::executable_dir().parent_path();
#ifdef _WIN32
    layout.python_home = layout.sdk_root / "python";
    layout.stdlib = layout.python_home / "Lib";
#else
    layout.python_home = layout.sdk_root;
    std::optional<fs::path> stdlib = find_linux_stdlib(layout.sdk_root);
    if (!stdlib.has_value()) {
        throw std::runtime_error(
            "bundled Python stdlib was not found under " +
            (layout.sdk_root / "lib").string());
    }
    layout.stdlib = *stdlib;
#endif
    layout.site_packages = layout.stdlib / "site-packages";

    std::error_code ec;
    if (!fs::is_directory(layout.stdlib, ec)) {
        throw std::runtime_error("bundled Python stdlib is missing: " + layout.stdlib.string());
    }
    if (!fs::is_directory(layout.site_packages, ec)) {
        throw std::runtime_error(
            "bundled Python site-packages is missing: " + layout.site_packages.string());
    }
    return layout;
}

std::string json_escape(const std::string& value) {
    std::string escaped;
    escaped.reserve(value.size());
    for (char character : value) {
        if (character == '\\' || character == '"') {
            escaped.push_back('\\');
        }
        escaped.push_back(character);
    }
    return escaped;
}

LauncherOptions parse_launcher_options(int argc, char** argv) {
    LauncherOptions options;
    options.python_args.emplace_back(argv[0]);

    int index = 1;
    while (index < argc) {
        const std::string argument = argv[index];
        if (argument == "--termin-info") {
            options.print_info = true;
            ++index;
            continue;
        }
        if (argument == "--termin-site") {
            if (index + 1 >= argc) {
                throw std::runtime_error("--termin-site requires a directory path");
            }
            fs::path site = fs::absolute(argv[index + 1]);
            std::error_code ec;
            site = fs::weakly_canonical(site, ec);
            if (ec || !fs::is_directory(site, ec)) {
                throw std::runtime_error("extra Python site directory is missing: " + site.string());
            }
            options.extra_sites.push_back(site);
            index += 2;
            continue;
        }
        if (argument == "--termin-overlay") {
            if (index + 1 >= argc) {
                throw std::runtime_error("--termin-overlay requires a manifest path");
            }
            fs::path manifest = fs::absolute(argv[index + 1]);
            std::error_code ec;
            manifest = fs::weakly_canonical(manifest, ec);
            if (ec || !fs::is_regular_file(manifest, ec)) {
                throw std::runtime_error(
                    "Python overlay manifest is missing: " + manifest.string());
            }
            options.overlay_manifest = manifest;
            index += 2;
            continue;
        }
        break;
    }
    for (; index < argc; ++index) {
        options.python_args.emplace_back(argv[index]);
    }
    return options;
}

void print_info(const PythonLayout& layout, const LauncherOptions& options) {
    std::cout
        << "{\n"
        << "  \"schema\": 1,\n"
        << "  \"sdk_root\": \"" << json_escape(layout.sdk_root.string()) << "\",\n"
        << "  \"python_home\": \"" << json_escape(layout.python_home.string()) << "\",\n"
        << "  \"stdlib\": \"" << json_escape(layout.stdlib.string()) << "\",\n"
        << "  \"site_packages\": \"" << json_escape(layout.site_packages.string()) << "\",\n"
        << "  \"isolated\": true,\n"
        << "  \"use_environment\": false,\n"
        << "  \"user_site\": false,\n"
        << "  \"overlay_manifest\": ";
    if (options.overlay_manifest.has_value()) {
        std::cout << "\"" << json_escape(options.overlay_manifest->string()) << "\"";
    } else {
        std::cout << "null";
    }
    std::cout
        << ",\n"
        << "  \"extra_sites\": [";
    for (std::size_t index = 0; index < options.extra_sites.size(); ++index) {
        if (index != 0) {
            std::cout << ", ";
        }
        std::cout << "\"" << json_escape(options.extra_sites[index].string()) << "\"";
    }
    std::cout
        << "]\n"
        << "}\n";
}

std::optional<int> report_status(const char* operation, PyStatus status, PyConfig* config) {
    if (!PyStatus_Exception(status)) {
        return std::nullopt;
    }
    std::cerr << "termin_python: " << operation << " failed";
    if (status.err_msg != nullptr) {
        std::cerr << ": " << status.err_msg;
    }
    std::cerr << std::endl;
    PyConfig_Clear(config);
    return PyStatus_IsExit(status) ? status.exitcode : 1;
}

int run_python(const PythonLayout& layout, const LauncherOptions& options) {
    termin_cli::python_backend::set_env_value("TERMIN_SDK", layout.sdk_root.string());

    PyConfig config;
    PyConfig_InitPythonConfig(&config);
    config.isolated = 1;
    config.use_environment = 0;
    config.user_site_directory = 0;
    config.site_import = 1;
    config.write_bytecode = 0;
    config.parse_argv = 1;

    const std::wstring home = layout.python_home.wstring();
    PyStatus status = PyConfig_SetString(&config, &config.home, home.c_str());
    if (std::optional<int> result = report_status("configuring Python home", status, &config)) {
        return *result;
    }

    std::vector<char*> python_argv;
    python_argv.reserve(options.python_args.size());
    for (const std::string& argument : options.python_args) {
        python_argv.push_back(const_cast<char*>(argument.c_str()));
    }
    status = PyConfig_SetBytesArgv(
        &config,
        static_cast<Py_ssize_t>(python_argv.size()),
        python_argv.data());
    if (std::optional<int> result = report_status("configuring Python arguments", status, &config)) {
        return *result;
    }

    status = Py_InitializeFromConfig(&config);
    if (std::optional<int> result = report_status("initializing bundled Python", status, &config)) {
        return *result;
    }
    PyConfig_Clear(&config);

    PyObject* sys_path = PySys_GetObject("path");
    if (sys_path == nullptr || !PyList_Check(sys_path)) {
        std::cerr << "termin_python: initialized Python has no sys.path list" << std::endl;
        return 1;
    }
    for (auto site = options.extra_sites.rbegin(); site != options.extra_sites.rend(); ++site) {
        PyObject* path = PyUnicode_DecodeFSDefault(site->string().c_str());
        if (path == nullptr || PyList_Insert(sys_path, 0, path) != 0) {
            Py_XDECREF(path);
            PyErr_Print();
            std::cerr << "termin_python: failed to add extra Python site: "
                      << site->string() << std::endl;
            return 1;
        }
        Py_DECREF(path);
    }
    if (options.overlay_manifest.has_value()) {
        PyObject* overlay_module = PyImport_ImportModule("termin_build.python_overlay");
        if (overlay_module == nullptr) {
            PyErr_Print();
            std::cerr << "termin_python: failed to import SDK overlay runtime" << std::endl;
            return 1;
        }
        PyObject* result = PyObject_CallMethod(
            overlay_module,
            "activate_overlay",
            "s",
            options.overlay_manifest->string().c_str());
        Py_DECREF(overlay_module);
        if (result == nullptr) {
            PyErr_Print();
            std::cerr << "termin_python: failed to activate Python overlay: "
                      << options.overlay_manifest->string() << std::endl;
            return 1;
        }
        Py_DECREF(result);
    }
    return Py_RunMain();
}

} // namespace

int main(int argc, char** argv) {
    try {
        const PythonLayout layout = resolve_layout();
        const LauncherOptions options = parse_launcher_options(argc, argv);
        if (options.print_info && options.python_args.size() == 1) {
            print_info(layout, options);
            return 0;
        }
        return run_python(layout, options);
    } catch (const std::exception& error) {
        std::cerr << "termin_python: " << error.what() << std::endl;
        return 1;
    }
}
