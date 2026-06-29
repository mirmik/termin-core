#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

#if defined(_WIN32)
#include <process.h>
#else
#include <cerrno>
#include <cstring>
#include <unistd.h>
#endif

namespace {

namespace fs = std::filesystem;

#if defined(_WIN32)
constexpr const char* kExeSuffix = ".exe";
constexpr char kPathSeparator = ';';
#else
constexpr const char* kExeSuffix = "";
constexpr char kPathSeparator = ':';
#endif

struct Dispatch {
    std::string executable;
    std::vector<std::string> args;
};

void print_help() {
    std::cout
        << "termin - Termin SDK command hub\n"
        << "\n"
        << "Usage:\n"
        << "  termin --help\n"
        << "  termin <command> [args...]\n"
        << "\n"
        << "Built-in commands:\n"
        << "  editor [project]       Run termin_editor.\n"
        << "  launcher               Run termin_launcher.\n"
        << "  shaderc [args...]      Run termin_shaderc.\n"
        << "  build <profile>        Run termin_builder build <profile>.\n"
        << "  run <profile>          Run packaged build output for a profile.\n"
        << "  play [scene]           Run project scene without building.\n"
        << "  modules [args...]      Warm up project modules and dependencies.\n"
        << "  profiles [args...]     Run termin_builder profiles [args...].\n"
        << "  profile <name>         Run termin_builder profile <name>.\n"
        << "  stdlib [args...]       Run termin_stdlib sync [args...].\n"
        << "  runner [args...]       Run termin_runner directly.\n"
        << "  builder [args...]      Run termin_builder directly.\n"
        << "\n"
        << "External commands:\n"
        << "  Unknown commands are resolved as termin_<command> or termin-<command>\n"
        << "  next to this executable, then in PATH.\n";
}

void print_usage_error() {
    std::cerr << "Usage: termin <command> [args...]\n"
              << "Run 'termin --help' for full help.\n";
}

bool has_directory_part(const std::string& path) {
    return path.find('/') != std::string::npos || path.find('\\') != std::string::npos;
}

fs::path find_in_path(const std::string& name) {
    const char* env_path = std::getenv("PATH");
    if (env_path == nullptr) {
        return {};
    }

    std::string paths(env_path);
    std::size_t start = 0;
    while (start <= paths.size()) {
        std::size_t end = paths.find(kPathSeparator, start);
        if (end == std::string::npos) {
            end = paths.size();
        }
        if (end > start) {
            fs::path candidate = fs::path(paths.substr(start, end - start)) / name;
            std::error_code ec;
            if (fs::exists(candidate, ec) && !fs::is_directory(candidate, ec)) {
                return candidate;
            }
        }
        if (end == paths.size()) {
            break;
        }
        start = end + 1;
    }
    return {};
}

fs::path executable_dir(const char* argv0) {
    fs::path self(argv0 != nullptr ? argv0 : "");
    if (!self.empty() && has_directory_part(self.string())) {
        std::error_code ec;
        fs::path resolved = fs::weakly_canonical(self, ec);
        if (!ec) {
            return resolved.parent_path();
        }
        return fs::absolute(self).parent_path();
    }

    fs::path found = find_in_path((self.empty() ? "termin" : self.string()) + std::string(kExeSuffix));
    if (found.empty() && !self.empty()) {
        found = find_in_path(self.string());
    }
    if (!found.empty()) {
        std::error_code ec;
        fs::path resolved = fs::weakly_canonical(found, ec);
        return (ec ? fs::absolute(found) : resolved).parent_path();
    }
    return fs::current_path();
}

fs::path find_executable(const fs::path& own_dir, const std::string& basename) {
    std::vector<std::string> names;
    names.push_back(basename + kExeSuffix);
#if defined(_WIN32)
    if (basename.size() < 4 || basename.substr(basename.size() - 4) != ".exe") {
        names.push_back(basename);
    }
#endif

    for (const std::string& name : names) {
        fs::path candidate = own_dir / name;
        std::error_code ec;
        if (fs::exists(candidate, ec) && !fs::is_directory(candidate, ec)) {
            return candidate;
        }
    }
    for (const std::string& name : names) {
        fs::path candidate = find_in_path(name);
        if (!candidate.empty()) {
            return candidate;
        }
    }
    return {};
}

std::vector<std::string> tail_args(int argc, char** argv, int start) {
    std::vector<std::string> result;
    for (int i = start; i < argc; ++i) {
        result.emplace_back(argv[i]);
    }
    return result;
}

Dispatch resolve_dispatch(int argc, char** argv, const fs::path& own_dir) {
    const std::string command = argv[1];
    Dispatch dispatch;

    auto direct = [&](const std::string& executable, int arg_start) {
        dispatch.executable = executable;
        dispatch.args = tail_args(argc, argv, arg_start);
    };

    if (command == "editor") {
        direct("termin_editor", 2);
    } else if (command == "launcher") {
        direct("termin_launcher", 2);
    } else if (command == "shaderc") {
        direct("termin_shaderc", 2);
    } else if (command == "build") {
        dispatch.executable = "termin_builder";
        dispatch.args.emplace_back("build");
        std::vector<std::string> rest = tail_args(argc, argv, 2);
        dispatch.args.insert(dispatch.args.end(), rest.begin(), rest.end());
    } else if (command == "run") {
        dispatch.executable = "termin_runner";
        dispatch.args.emplace_back("run");
        std::vector<std::string> rest = tail_args(argc, argv, 2);
        dispatch.args.insert(dispatch.args.end(), rest.begin(), rest.end());
    } else if (command == "play") {
        dispatch.executable = "termin_runner";
        dispatch.args.emplace_back("play");
        std::vector<std::string> rest = tail_args(argc, argv, 2);
        dispatch.args.insert(dispatch.args.end(), rest.begin(), rest.end());
    } else if (command == "modules") {
        direct("termin_modules_cli", 2);
    } else if (command == "profiles") {
        dispatch.executable = "termin_builder";
        dispatch.args.emplace_back("profiles");
        std::vector<std::string> rest = tail_args(argc, argv, 2);
        dispatch.args.insert(dispatch.args.end(), rest.begin(), rest.end());
    } else if (command == "profile") {
        dispatch.executable = "termin_builder";
        dispatch.args.emplace_back("profile");
        std::vector<std::string> rest = tail_args(argc, argv, 2);
        dispatch.args.insert(dispatch.args.end(), rest.begin(), rest.end());
    } else if (command == "stdlib") {
        dispatch.executable = "termin_stdlib";
        std::vector<std::string> rest = tail_args(argc, argv, 2);
        if (rest.empty() || (!rest.front().empty() && rest.front()[0] == '-')) {
            dispatch.args.emplace_back("sync");
        }
        dispatch.args.insert(dispatch.args.end(), rest.begin(), rest.end());
    } else if (command == "builder") {
        direct("termin_builder", 2);
    } else if (command == "runner") {
        direct("termin_runner", 2);
    } else {
        fs::path underscore = find_executable(own_dir, "termin_" + command);
        if (!underscore.empty()) {
            dispatch.executable = underscore.string();
            dispatch.args = tail_args(argc, argv, 2);
            return dispatch;
        }
        fs::path dash = find_executable(own_dir, "termin-" + command);
        if (!dash.empty()) {
            dispatch.executable = dash.string();
            dispatch.args = tail_args(argc, argv, 2);
            return dispatch;
        }
        throw std::runtime_error("unknown command: " + command);
    }

    fs::path resolved = find_executable(own_dir, dispatch.executable);
    if (resolved.empty()) {
        throw std::runtime_error("command executable not found: " + dispatch.executable);
    }
    dispatch.executable = resolved.string();
    return dispatch;
}

int run_child(const Dispatch& dispatch) {
    std::vector<std::string> storage;
    storage.reserve(dispatch.args.size() + 1);
    storage.push_back(dispatch.executable);
    storage.insert(storage.end(), dispatch.args.begin(), dispatch.args.end());

    std::vector<char*> argv;
    argv.reserve(storage.size() + 1);
    for (std::string& arg : storage) {
        argv.push_back(arg.data());
    }
    argv.push_back(nullptr);

#if defined(_WIN32)
    int code = _spawnv(_P_WAIT, dispatch.executable.c_str(), argv.data());
    if (code == -1) {
        std::cerr << "termin: failed to run " << dispatch.executable << "\n";
        return 127;
    }
    return code;
#else
    execv(dispatch.executable.c_str(), argv.data());
    std::cerr << "termin: failed to exec " << dispatch.executable << ": "
              << std::strerror(errno) << "\n";
    return 127;
#endif
}

} // namespace

int main(int argc, char** argv) {
    if (argc <= 1) {
        print_usage_error();
        return 2;
    }

    const std::string first = argv[1];
    if (first == "--help" || first == "-h" || first == "help") {
        print_help();
        return 0;
    }

    try {
        Dispatch dispatch = resolve_dispatch(argc, argv, executable_dir(argv[0]));
        return run_child(dispatch);
    } catch (const std::exception& exc) {
        std::cerr << "termin: " << exc.what() << "\n";
        print_usage_error();
        return 2;
    }
}
