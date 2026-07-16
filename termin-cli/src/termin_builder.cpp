#include "termin_python_backend.hpp"

#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

namespace fs = std::filesystem;

constexpr const char* kDefaultProfilePath = "project_settings/build_profiles.json";

struct GlobalOptions {
    fs::path project_root;
    fs::path profiles_path;
    fs::path request_output;
    bool dry_run = false;
};

struct ParsedArgs {
    std::string command;
    std::string profile_name;
    GlobalOptions options;
};

void print_help() {
    std::cout
        << "termin_builder - Termin project build profile utility\n"
        << "\n"
        << "Usage:\n"
        << "  termin_builder --help\n"
        << "  termin_builder profiles [--project <dir>] [--profiles <file>]\n"
        << "  termin_builder profile <name> [--project <dir>] [--profiles <file>]\n"
        << "  termin_builder build <name> [--project <dir>] [--profiles <file>] [--dry-run]\n"
        << "\n"
        << "Profile file:\n"
        << "  project_settings/build_profiles.json\n"
        << "\n"
        << "Schema v2 profile excerpt:\n"
        << "  {\n"
        << "    \"version\": 2,\n"
        << "    \"profiles\": {\n"
        << "      \"dev\": {\n"
        << "        \"target\": {\"kind\": \"desktop\", \"os\": \"linux\", \"arch\": \"x86_64\"},\n"
        << "        \"configuration\": \"dev\",\n"
        << "        \"content\": {\n"
        << "          \"entry_scene\": \"Scenes/Main.scene\",\n"
        << "          \"scenes\": [\"Scenes/Main.scene\"]\n"
        << "        },\n"
        << "        \"runtime\": {\"backends\": [\"vulkan\", \"opengl\"]}\n"
        << "      }\n"
        << "    }\n"
        << "  }\n";
}

void print_usage_error() {
    std::cerr
        << "Usage: termin_builder profiles|profile <name>|build <name> [options]\n"
        << "Run 'termin_builder --help' for full help.\n";
}

ParsedArgs parse_args(int argc, char** argv) {
    ParsedArgs parsed;
    if (argc >= 2) {
        const std::string first = argv[1];
        if (first == "--help" || first == "-h" || first == "help") {
            parsed.command = "help";
            return parsed;
        }
    }
    if (argc < 2) {
        throw std::runtime_error("missing command");
    }

    parsed.command = argv[1];
    if (parsed.command != "profiles" && parsed.command != "profile" && parsed.command != "build"
        && parsed.command != "resolve") {
        throw std::runtime_error("unknown command: " + parsed.command);
    }

    int i = 2;
    if (parsed.command == "profile" || parsed.command == "build" || parsed.command == "resolve") {
        if (i >= argc || std::string(argv[i]).rfind("-", 0) == 0) {
            throw std::runtime_error("missing profile name");
        }
        parsed.profile_name = argv[i++];
    }

    for (; i < argc; ++i) {
        const std::string arg = argv[i];
        auto take_value = [&]() -> std::string {
            if (i + 1 >= argc) {
                throw std::runtime_error("missing value for " + arg);
            }
            return argv[++i];
        };

        if (arg == "--project") {
            parsed.options.project_root = take_value();
        } else if (arg == "--profiles") {
            parsed.options.profiles_path = take_value();
        } else if (arg == "--request-output" && parsed.command == "resolve") {
            parsed.options.request_output = take_value();
        } else if (arg == "--dry-run") {
            parsed.options.dry_run = true;
        } else {
            throw std::runtime_error("unknown option: " + arg);
        }
    }
    if (parsed.command == "resolve" && parsed.options.request_output.empty()) {
        throw std::runtime_error("resolve requires --request-output");
    }
    return parsed;
}

bool has_termin_project_file(const fs::path& dir) {
    std::error_code ec;
    if (!fs::exists(dir, ec) || !fs::is_directory(dir, ec)) {
        return false;
    }
    for (const fs::directory_entry& entry : fs::directory_iterator(dir, ec)) {
        if (ec) {
            return false;
        }
        if (entry.is_regular_file(ec) && entry.path().extension() == ".terminproj") {
            return true;
        }
    }
    return false;
}

fs::path find_project_root(const fs::path& requested) {
    fs::path start = requested.empty() ? fs::current_path() : requested;
    start = fs::absolute(start);
    std::error_code ec;
    start = fs::weakly_canonical(start, ec);
    if (ec) {
        start = fs::absolute(requested.empty() ? fs::current_path() : requested);
    }
    if (fs::is_regular_file(start, ec)) {
        start = start.parent_path();
    }

    for (fs::path dir = start; !dir.empty(); dir = dir.parent_path()) {
        if (has_termin_project_file(dir)) {
            return dir;
        }
        if (dir == dir.root_path()) {
            break;
        }
    }
    throw std::runtime_error("could not find a .terminproj file from: " + start.string());
}

fs::path resolve_profiles_path(const GlobalOptions& options, const fs::path& project_root) {
    if (options.profiles_path.empty()) {
        return project_root / kDefaultProfilePath;
    }
    fs::path path = options.profiles_path;
    if (!path.is_absolute()) {
        path = fs::current_path() / path;
    }
    return fs::absolute(path);
}

std::vector<std::string> profile_backend_command(
    const ParsedArgs& args,
    const fs::path& project_root,
    const fs::path& profiles_path
) {
    std::vector<std::string> command =
        termin_cli::python_backend::python_module_command("termin.project_build.profile_build");
    command.push_back(args.command);
    command.insert(command.end(), {
        "--project-root",
        project_root.string(),
        "--profiles-path",
        profiles_path.string(),
    });
    if (!args.profile_name.empty()) {
        command.insert(command.end(), {"--profile", args.profile_name});
    }
    if (args.command == "build" && args.options.dry_run) {
        command.push_back("--dry-run");
    }
    if (args.command == "resolve") {
        command.insert(command.end(), {
            "--request-output",
            fs::absolute(args.options.request_output).string(),
        });
    }
    return command;
}

int run_profile_backend(const ParsedArgs& args) {
    const fs::path project_root = find_project_root(args.options.project_root);
    const fs::path profiles_path = resolve_profiles_path(args.options, project_root);
    termin_cli::python_backend::configure_environment();
    const std::vector<std::string> command =
        profile_backend_command(args, project_root, profiles_path);
    return termin_cli::python_backend::run_process(command, "build profile backend");
}

} // namespace

int main(int argc, char** argv) {
    try {
        const ParsedArgs args = parse_args(argc, argv);
        if (args.command == "help") {
            print_help();
            return 0;
        }
        return run_profile_backend(args);
    } catch (const std::exception& exc) {
        std::cerr << "termin_builder: " << exc.what() << "\n";
        print_usage_error();
        return 2;
    }
}
