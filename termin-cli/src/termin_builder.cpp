#include "termin_python_backend.hpp"

#include <tcbase/trent/json.h>
#include <tcbase/trent/trent.h>

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
    bool dry_run = false;
};

struct ParsedArgs {
    std::string command;
    std::string profile_name;
    GlobalOptions options;
};

struct BuildProfile {
    std::string name;
    std::string target;
    std::string entry_scene;
    std::string output_dir;
    const nos::trent* raw = nullptr;
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
        << "Expected schema:\n"
        << "  {\n"
        << "    \"profiles\": {\n"
        << "      \"dev\": {\n"
        << "        \"target\": \"desktop\",\n"
        << "        \"entry_scene\": \"Main.scene\",\n"
        << "        \"output_dir\": \"dist/dev\"\n"
        << "      }\n"
        << "    }\n"
        << "  }\n";
}

void print_usage_error() {
    std::cerr
        << "Usage: termin_builder profiles|profile <name>|build <name> [options]\n"
        << "Run 'termin_builder --help' for full help.\n";
}

bool is_option_with_value(const std::string& arg) {
    return arg == "--project" || arg == "--profiles";
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
    if (parsed.command != "profiles" && parsed.command != "profile" && parsed.command != "build") {
        throw std::runtime_error("unknown command: " + parsed.command);
    }

    int i = 2;
    if (parsed.command == "profile" || parsed.command == "build") {
        if (i >= argc || std::string(argv[i]).rfind("-", 0) == 0) {
            throw std::runtime_error("missing profile name");
        }
        parsed.profile_name = argv[i++];
    }

    for (; i < argc; ++i) {
        std::string arg = argv[i];
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
        } else if (arg == "--dry-run") {
            parsed.options.dry_run = true;
        } else if (is_option_with_value(arg)) {
            (void)take_value();
        } else {
            throw std::runtime_error("unknown option: " + arg);
        }
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
    if (!options.profiles_path.empty()) {
        fs::path path = options.profiles_path;
        if (!path.is_absolute()) {
            path = fs::current_path() / path;
        }
        return fs::absolute(path);
    }
    return project_root / kDefaultProfilePath;
}

const nos::trent& profile_map(const nos::trent& root) {
    if (!root.is_dict()) {
        throw std::runtime_error("build profiles root must be a JSON object");
    }
    const nos::trent* profiles = root._get("profiles");
    if (profiles == nullptr) {
        throw std::runtime_error("build profiles file must contain a 'profiles' object");
    }
    if (!profiles->is_dict()) {
        throw std::runtime_error("'profiles' must be a JSON object");
    }
    return *profiles;
}

std::string optional_string_field(const nos::trent& object, const char* key) {
    const nos::trent* value = object._get(key);
    if (value == nullptr || value->is_nil()) {
        return "";
    }
    if (!value->is_string()) {
        throw std::runtime_error(std::string("profile field must be a string: ") + key);
    }
    return value->as_string();
}

BuildProfile read_profile(const std::string& name, const nos::trent& value) {
    if (!value.is_dict()) {
        throw std::runtime_error("profile '" + name + "' must be a JSON object");
    }

    BuildProfile profile;
    profile.name = name;
    profile.raw = &value;
    profile.target = optional_string_field(value, "target");
    profile.entry_scene = optional_string_field(value, "entry_scene");
    profile.output_dir = optional_string_field(value, "output_dir");

    if (profile.target.empty()) {
        throw std::runtime_error("profile '" + name + "' has no target");
    }
    if (profile.entry_scene.empty()) {
        throw std::runtime_error("profile '" + name + "' has no entry_scene");
    }
    if (profile.output_dir.empty()) {
        throw std::runtime_error("profile '" + name + "' has no output_dir");
    }
    return profile;
}

nos::trent load_profiles_file(const fs::path& path) {
    std::error_code ec;
    if (!fs::exists(path, ec)) {
        throw std::runtime_error("build profiles file does not exist: " + path.string());
    }
    return nos::json::parse_file(path.string());
}

void list_profiles(const nos::trent& profiles) {
    const auto& dict = profiles.as_dict_except();
    if (dict.empty()) {
        std::cout << "No build profiles defined.\n";
        return;
    }
    for (const auto& item : dict) {
        std::cout << item.first;
        if (item.second.is_dict()) {
            const std::string target = optional_string_field(item.second, "target");
            if (!target.empty()) {
                std::cout << " (" << target << ")";
            }
        }
        std::cout << "\n";
    }
}

BuildProfile find_profile(const nos::trent& profiles, const std::string& name) {
    const nos::trent* value = profiles._get(name);
    if (value == nullptr) {
        throw std::runtime_error("unknown build profile: " + name);
    }
    return read_profile(name, *value);
}

void print_profile_summary(const fs::path& project_root, const fs::path& profiles_path, const BuildProfile& profile) {
    std::cout
        << "Profile: " << profile.name << "\n"
        << "Project: " << project_root << "\n"
        << "Profiles: " << profiles_path << "\n"
        << "Target: " << profile.target << "\n"
        << "Entry scene: " << profile.entry_scene << "\n"
        << "Output dir: " << profile.output_dir << "\n";
}

int command_profiles(const GlobalOptions& options) {
    fs::path project_root = find_project_root(options.project_root);
    fs::path profiles_path = resolve_profiles_path(options, project_root);
    nos::trent root = load_profiles_file(profiles_path);

    std::cout << "Project: " << project_root << "\n";
    std::cout << "Profiles: " << profiles_path << "\n";
    list_profiles(profile_map(root));
    return 0;
}

int command_profile(const ParsedArgs& args) {
    fs::path project_root = find_project_root(args.options.project_root);
    fs::path profiles_path = resolve_profiles_path(args.options, project_root);
    nos::trent root = load_profiles_file(profiles_path);
    BuildProfile profile = find_profile(profile_map(root), args.profile_name);
    print_profile_summary(project_root, profiles_path, profile);
    return 0;
}

int command_build(const ParsedArgs& args) {
    fs::path project_root = find_project_root(args.options.project_root);
    fs::path profiles_path = resolve_profiles_path(args.options, project_root);
    nos::trent root = load_profiles_file(profiles_path);
    BuildProfile profile = find_profile(profile_map(root), args.profile_name);
    print_profile_summary(project_root, profiles_path, profile);

    if (args.options.dry_run) {
        std::cout << "Dry run: build execution skipped.\n";
        return 0;
    }

    termin_cli::python_backend::configure_environment();
    std::vector<std::string> command =
        termin_cli::python_backend::python_module_command("termin.project_build.profile_build");
    command.insert(command.end(), {
        "build",
        "--project-root",
        project_root.string(),
        "--profiles-path",
        profiles_path.string(),
        "--profile",
        profile.name,
        "--target",
        profile.target,
    });

    std::cout << "Executing " << profile.target << " build backend...\n" << std::flush;
    return termin_cli::python_backend::run_process(command, "build backend");
}

} // namespace

int main(int argc, char** argv) {
    try {
        ParsedArgs args = parse_args(argc, argv);
        if (args.command == "help") {
            print_help();
            return 0;
        }
        if (args.command == "profiles") {
            return command_profiles(args.options);
        }
        if (args.command == "profile") {
            return command_profile(args);
        }
        if (args.command == "build") {
            return command_build(args);
        }
        throw std::runtime_error("unknown command: " + args.command);
    } catch (const std::exception& exc) {
        std::cerr << "termin_builder: " << exc.what() << "\n";
        print_usage_error();
        return 2;
    }
}
