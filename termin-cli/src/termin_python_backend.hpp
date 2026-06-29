#pragma once

#include <cstdlib>
#include <cstdio>
#include <filesystem>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#ifdef _WIN32
#include <process.h>
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace termin_cli::python_backend {

namespace fs = std::filesystem;

inline fs::path executable_dir() {
#ifdef _WIN32
    std::vector<char> buffer(MAX_PATH);
    DWORD size = GetModuleFileNameA(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    while (size == buffer.size()) {
        buffer.resize(buffer.size() * 2);
        size = GetModuleFileNameA(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    }
    if (size == 0) {
        return fs::current_path();
    }
    return fs::path(std::string(buffer.data(), size)).parent_path();
#else
    std::vector<char> buffer(4096);
    ssize_t size = readlink("/proc/self/exe", buffer.data(), buffer.size() - 1);
    if (size <= 0) {
        return fs::current_path();
    }
    buffer[static_cast<size_t>(size)] = '\0';
    return fs::path(buffer.data()).parent_path();
#endif
}

inline std::string env_path_separator() {
#ifdef _WIN32
    return ";";
#else
    return ":";
#endif
}

inline std::string current_env(const char* name) {
    const char* value = std::getenv(name);
    return value == nullptr ? std::string() : std::string(value);
}

inline void set_env_value(const char* name, const std::string& value) {
#ifdef _WIN32
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 1);
#endif
}

inline void prepend_env_path(const char* name, const fs::path& value) {
    if (value.empty()) {
        return;
    }
    std::string current = current_env(name);
    std::string next = value.string();
    if (!current.empty()) {
        next += env_path_separator();
        next += current;
    }
    set_env_value(name, next);
}

inline void append_python_prefix_paths(std::vector<fs::path>& paths, const fs::path& prefix_root) {
#ifdef _WIN32
    fs::path windows_site_packages = prefix_root / "python" / "Lib" / "site-packages";
    std::error_code ec;
    if (fs::exists(windows_site_packages, ec)) {
        paths.push_back(windows_site_packages);
    }
#else
    const fs::path lib_dir = prefix_root / "lib";
    std::error_code ec;
    if (fs::exists(lib_dir, ec)) {
        for (const fs::directory_entry& entry : fs::directory_iterator(lib_dir, ec)) {
            if (ec) {
                break;
            }
            if (!entry.is_directory(ec)) {
                continue;
            }
            const std::string name = entry.path().filename().string();
            if (name.rfind("python3.", 0) == 0) {
                fs::path site_packages = entry.path() / "site-packages";
                if (fs::exists(site_packages, ec)) {
                    paths.push_back(site_packages);
                }
            }
        }
    }
#endif

    fs::path sdk_python = prefix_root / "lib" / "python";
    if (fs::exists(sdk_python, ec)) {
        paths.push_back(sdk_python);
    }
}

inline std::vector<fs::path> python_module_paths(const fs::path& install_root, const fs::path& exe_dir) {
    std::vector<fs::path> paths;
    std::error_code ec;
    append_python_prefix_paths(paths, install_root);
    append_python_prefix_paths(paths, install_root / "sdk-install-staging");

    for (fs::path dir = exe_dir; !dir.empty(); dir = dir.parent_path()) {
        append_python_prefix_paths(paths, dir / "sdk");
        const std::pair<const char*, const char*> dev_packages[] = {
            {"termin-app", "__init__.py"},
            {"termin-player", "player/__init__.py"},
            {"termin-mcp", "mcp/__init__.py"},
        };
        bool found_dev_checkout = false;
        for (const auto& [package_dir_name, package_probe] : dev_packages) {
            fs::path dev_python = dir / package_dir_name;
            if (fs::exists(dev_python / "termin" / package_probe, ec)) {
                paths.push_back(dev_python);
                found_dev_checkout = true;
            }
        }
        if (found_dev_checkout) {
            break;
        }
        if (dir == dir.root_path()) {
            break;
        }
    }

    return paths;
}

inline void configure_environment() {
    fs::path exe_dir = executable_dir();
    fs::path install_root = exe_dir.parent_path();

    if (current_env("TERMIN_SDK").empty()) {
        set_env_value("TERMIN_SDK", install_root.string());
    }
    prepend_env_path("PATH", exe_dir);

    std::string pythonpath_prefix;
    for (const fs::path& path : python_module_paths(install_root, exe_dir)) {
        if (!fs::exists(path)) {
            continue;
        }
        if (!pythonpath_prefix.empty()) {
            pythonpath_prefix += env_path_separator();
        }
        pythonpath_prefix += path.string();
    }
    std::string pythonpath = current_env("PYTHONPATH");
    if (!pythonpath_prefix.empty()) {
        if (!pythonpath.empty()) {
            pythonpath = pythonpath_prefix + env_path_separator() + pythonpath;
        } else {
            pythonpath = pythonpath_prefix;
        }
    }
    if (!pythonpath.empty()) {
        set_env_value("PYTHONPATH", pythonpath);
    }
}

inline std::optional<fs::path> bundled_python_executable(const fs::path& install_root) {
#ifdef _WIN32
    std::vector<fs::path> candidates = {
        install_root / "python" / "python.exe",
        install_root / "bin" / "python.exe",
    };
#else
    std::vector<fs::path> candidates = {
        install_root / "bin" / "python3",
        install_root / "bin" / "python",
    };
#endif
    std::error_code ec;
    for (const fs::path& candidate : candidates) {
        if (fs::exists(candidate, ec) && fs::is_regular_file(candidate, ec)) {
            return candidate;
        }
    }
    return std::nullopt;
}

inline std::vector<std::string> python_module_command(const std::string& module_name) {
    fs::path install_root = executable_dir().parent_path();
    if (std::optional<fs::path> python = bundled_python_executable(install_root)) {
        return {
            python->string(),
            "-m",
            module_name,
        };
    }
    return {
#ifdef _WIN32
        "python",
#else
        "python3",
#endif
        "-m",
        module_name,
    };
}

inline int run_process(const std::vector<std::string>& args, const char* process_label) {
    if (args.empty()) {
        throw std::runtime_error("cannot run empty command");
    }

#ifdef _WIN32
    (void)process_label;
    std::vector<const char*> argv;
    argv.reserve(args.size() + 1);
    for (const std::string& arg : args) {
        argv.push_back(arg.c_str());
    }
    argv.push_back(nullptr);
    int code = _spawnvp(_P_WAIT, args.front().c_str(), argv.data());
    if (code == -1) {
        throw std::runtime_error("failed to run " + args.front());
    }
    return code;
#else
    pid_t pid = fork();
    if (pid < 0) {
        throw std::runtime_error(std::string("failed to fork ") + process_label + " process");
    }
    if (pid == 0) {
        std::vector<char*> argv;
        argv.reserve(args.size() + 1);
        for (const std::string& arg : args) {
            argv.push_back(const_cast<char*>(arg.c_str()));
        }
        argv.push_back(nullptr);
        execvp(args.front().c_str(), argv.data());
        std::perror(args.front().c_str());
        _exit(127);
    }

    int status = 0;
    if (waitpid(pid, &status, 0) < 0) {
        throw std::runtime_error(std::string("failed to wait for ") + process_label + " process");
    }
    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    if (WIFSIGNALED(status)) {
        return 128 + WTERMSIG(status);
    }
    return 1;
#endif
}

} // namespace termin_cli::python_backend
