#include "termin_python_backend.hpp"

#include <tcbase/trent/json.h>
#include <tcbase/trent/trent.h>

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <iostream>
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

namespace {

namespace fs = std::filesystem;

constexpr const char* kDefaultProfilePath = "project_settings/build_profiles.json";

struct RunnerOptions {
    fs::path project_root;
    fs::path profiles_path;
    std::string mode = "build";
    bool build_if_missing = false;
    bool rebuild = false;
    bool dry_run = false;
    std::optional<std::string> backend;
    std::optional<std::string> scene_override;
    std::vector<std::string> player_args;
};

struct ParsedArgs {
    std::string command;
    std::string profile_name;
    std::optional<std::string> play_scene;
    RunnerOptions options;
};

struct BuildProfile {
    std::string name;
    std::string target;
    std::string entry_scene;
    std::string output_dir;
};

void set_env_value(const char* name, const std::string& value) {
    termin_cli::python_backend::set_env_value(name, value);
}

void configure_python_backend_environment() {
    termin_cli::python_backend::configure_environment();
}

int run_process(const std::vector<std::string>& args) {
    return termin_cli::python_backend::run_process(args, "runner backend");
}

void print_help() {
    std::cout
        << "termin_runner - Termin project run/play utility\n"
        << "\n"
        << "Usage:\n"
        << "  termin_runner --help\n"
        << "  termin_runner run <profile> [--project <dir>] [--profiles <file>] [options] [-- player-args...]\n"
        << "  termin_runner play [project|scene] [--project <dir>] [options] [-- player-args...]\n"
        << "\n"
        << "Run-only options:\n"
        << "  --profiles <file>         Override project_settings/build_profiles.json.\n"
        << "  --mode build|project\n"
        << "                            Run packaged build output or source project scene.\n"
        << "  --build-if-missing        Build the profile if build output is missing.\n"
        << "  --rebuild                 Build the profile before running.\n"
        << "\n"
        << "Shared/play options:\n"
        << "  --dry-run                 Print the resolved command without executing it.\n"
        << "  --backend <name>          Set TERMIN_BACKEND for the player process.\n"
        << "  --scene <path>            Select source scene for play/project mode.\n"
        << "  --headless                Forward to termin.player source project headless mode.\n"
        << "  --frames <count>          Limit termin.player --headless to a finite frame count.\n"
        << "  --dt <seconds>            Forward to termin.player --headless timestep.\n"
        << "  --width <pixels>          Forward to termin.player.\n"
        << "  --height <pixels>         Forward to termin.player.\n"
        << "  --title <text>            Forward to termin.player.\n"
        << "  --windowed                Forward to termin.player normal-window mode.\n"
        << "  --mcp                     Enable player MCP diagnostics endpoint.\n"
        << "  --mcp-host <host>         Forward player MCP bind host.\n"
        << "  --mcp-port <port>         Forward player MCP bind port.\n"
        << "  --mcp-token <token>       Forward player MCP bearer token.\n"
        << "  --mcp-session-file <path> Forward player MCP session file path.\n";
}

void print_usage_error() {
    std::cerr
        << "Usage: termin_runner run <profile> [options]\n"
        << "       termin_runner play [project|scene] [options]\n"
        << "Run 'termin_runner --help' for full help.\n";
}

std::string take_value(int argc, char** argv, int& index, const std::string& option) {
    if (index + 1 >= argc) {
        throw std::runtime_error("missing value for " + option);
    }
    return argv[++index];
}

bool positional_play_arg_is_project(const std::string& value) {
    if (value.empty()) {
        return false;
    }

    std::error_code ec;
    fs::path path = fs::absolute(fs::path(value));
    path = fs::weakly_canonical(path, ec);
    if (ec) {
        path = fs::absolute(fs::path(value));
    }

    if (fs::is_directory(path, ec)) {
        return true;
    }
    if (fs::is_regular_file(path, ec) && path.extension() == ".terminproj") {
        return true;
    }
    return false;
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
    if (parsed.command != "run" && parsed.command != "play") {
        throw std::runtime_error("unknown command: " + parsed.command);
    }

    int i = 2;
    if (parsed.command == "run") {
        if (i >= argc || std::string(argv[i]).rfind("-", 0) == 0) {
            throw std::runtime_error("missing profile name");
        }
        parsed.profile_name = argv[i++];
    } else if (i < argc && std::string(argv[i]).rfind("-", 0) != 0) {
        std::string value = argv[i++];
        if (positional_play_arg_is_project(value)) {
            parsed.options.project_root = value;
        } else {
            parsed.play_scene = value;
        }
    }

    for (; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--") {
            for (++i; i < argc; ++i) {
                parsed.options.player_args.emplace_back(argv[i]);
            }
            break;
        }
        if (arg == "--project") {
            parsed.options.project_root = take_value(argc, argv, i, arg);
        } else if (arg == "--profiles") {
            if (parsed.command == "play") {
                throw std::runtime_error("--profiles is only supported by run");
            }
            parsed.options.profiles_path = take_value(argc, argv, i, arg);
        } else if (arg == "--mode") {
            if (parsed.command == "play") {
                throw std::runtime_error("--mode is only supported by run");
            }
            parsed.options.mode = take_value(argc, argv, i, arg);
        } else if (arg == "--build-if-missing") {
            if (parsed.command == "play") {
                throw std::runtime_error("--build-if-missing is only supported by run");
            }
            parsed.options.build_if_missing = true;
        } else if (arg == "--rebuild") {
            if (parsed.command == "play") {
                throw std::runtime_error("--rebuild is only supported by run");
            }
            parsed.options.rebuild = true;
        } else if (arg == "--dry-run") {
            parsed.options.dry_run = true;
        } else if (arg == "--backend") {
            parsed.options.backend = take_value(argc, argv, i, arg);
        } else if (arg == "--scene") {
            if (parsed.play_scene.has_value()) {
                throw std::runtime_error("scene specified both positionally and with --scene");
            }
            parsed.options.scene_override = take_value(argc, argv, i, arg);
        } else if (arg == "--headless" || arg == "--no-assets" ||
                   arg == "--no-modules" || arg == "--windowed") {
            parsed.options.player_args.emplace_back(arg);
        } else if (arg == "--frames" || arg == "--dt") {
            parsed.options.player_args.emplace_back(arg);
            parsed.options.player_args.emplace_back(take_value(argc, argv, i, arg));
        } else if (arg == "--mcp") {
            parsed.options.player_args.emplace_back(arg);
        } else if (arg == "--mcp-host" || arg == "--mcp-port" ||
                   arg == "--mcp-token" || arg == "--mcp-session-file") {
            parsed.options.player_args.emplace_back(arg);
            parsed.options.player_args.emplace_back(take_value(argc, argv, i, arg));
        } else if (arg == "--width" || arg == "--height" || arg == "--title" ||
                   arg == "-W" || arg == "-H" || arg == "-t") {
            parsed.options.player_args.emplace_back(arg);
            parsed.options.player_args.emplace_back(take_value(argc, argv, i, arg));
        } else {
            throw std::runtime_error("unknown option: " + arg);
        }
    }

    if (parsed.command == "run" &&
        parsed.options.mode != "build" && parsed.options.mode != "project") {
        throw std::runtime_error("unsupported run mode: " + parsed.options.mode);
    }
    if (parsed.options.rebuild) {
        parsed.options.build_if_missing = true;
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

std::optional<fs::path> relative_project_path(const fs::path& project_root, const fs::path& path) {
    std::error_code ec;
    fs::path root = fs::weakly_canonical(project_root, ec);
    if (ec) {
        root = fs::absolute(project_root);
    }
    fs::path resolved = fs::weakly_canonical(path, ec);
    if (ec) {
        return std::nullopt;
    }

    fs::path rel = fs::relative(resolved, root, ec);
    if (ec || rel.empty() || rel.is_absolute()) {
        return std::nullopt;
    }
    for (const fs::path& part : rel) {
        if (part == "..") {
            return std::nullopt;
        }
    }
    return rel;
}

std::optional<std::string> resolve_scene_candidate(
    const fs::path& project_root,
    const std::string& value,
    const std::string& source,
    bool strict
) {
    if (value.empty()) {
        if (strict) {
            throw std::runtime_error(source + " scene is empty");
        }
        return std::nullopt;
    }

    fs::path scene_path = value;
    if (!scene_path.is_absolute()) {
        scene_path = project_root / scene_path;
    }

    std::error_code ec;
    fs::path resolved = fs::weakly_canonical(scene_path, ec);
    if (ec) {
        resolved = fs::absolute(scene_path);
    }

    auto fail = [&](const std::string& message) -> std::optional<std::string> {
        std::string full = source + " scene is not usable: " + message + ": " + resolved.string();
        if (strict) {
            throw std::runtime_error(full);
        }
        std::cerr << "termin_runner: " << full << "\n";
        return std::nullopt;
    };

    if (!fs::exists(resolved, ec) || !fs::is_regular_file(resolved, ec)) {
        return fail("file does not exist");
    }
    if (resolved.extension() != ".scene") {
        return fail("expected a .scene file");
    }

    std::optional<fs::path> rel = relative_project_path(project_root, resolved);
    if (!rel.has_value()) {
        return fail("file is outside project root");
    }
    return rel->generic_string();
}

std::optional<std::string> read_last_scene_from_project_state(const fs::path& project_root) {
    fs::path state_path = project_root / "project_settings" / ".editor_state.json";
    std::error_code ec;
    if (!fs::exists(state_path, ec)) {
        return std::nullopt;
    }

    try {
        nos::trent state = nos::json::parse_file(state_path.string());
        if (!state.is_dict()) {
            std::cerr << "termin_runner: editor state root is not an object: "
                      << state_path << "\n";
            return std::nullopt;
        }
        const nos::trent* last_scene = state._get("last_scene");
        if (last_scene == nullptr || last_scene->is_nil()) {
            return std::nullopt;
        }
        if (!last_scene->is_string()) {
            std::cerr << "termin_runner: editor state last_scene is not a string: "
                      << state_path << "\n";
            return std::nullopt;
        }
        return last_scene->as_string();
    } catch (const std::exception& exc) {
        std::cerr << "termin_runner: failed to read editor state "
                  << state_path << ": " << exc.what() << "\n";
        return std::nullopt;
    }
}

std::optional<std::string> find_first_project_scene(const fs::path& project_root) {
    std::vector<fs::path> scenes;
    std::error_code ec;
    fs::recursive_directory_iterator it(
        project_root,
        fs::directory_options::skip_permission_denied,
        ec
    );
    fs::recursive_directory_iterator end;
    for (; !ec && it != end; it.increment(ec)) {
        const fs::directory_entry& entry = *it;
        const fs::path filename = entry.path().filename();
        if (entry.is_directory(ec)) {
            const std::string name = filename.string();
            if (name == "project_settings" || name.rfind(".", 0) == 0 ||
                name.rfind("__", 0) == 0) {
                it.disable_recursion_pending();
            }
            continue;
        }
        if (entry.is_regular_file(ec) && entry.path().extension() == ".scene") {
            if (auto rel = relative_project_path(project_root, entry.path())) {
                scenes.push_back(*rel);
            }
        }
    }
    if (ec) {
        std::cerr << "termin_runner: failed to scan project scenes: "
                  << ec.message() << "\n";
    }
    if (scenes.empty()) {
        return std::nullopt;
    }
    std::sort(scenes.begin(), scenes.end());
    return scenes.front().generic_string();
}

std::string resolve_play_scene(const fs::path& project_root, const ParsedArgs& args) {
    if (args.options.scene_override.has_value()) {
        return *resolve_scene_candidate(
            project_root,
            *args.options.scene_override,
            "--scene",
            true
        );
    }
    if (args.play_scene.has_value()) {
        return *resolve_scene_candidate(project_root, *args.play_scene, "positional", true);
    }

    if (std::optional<std::string> last_scene = read_last_scene_from_project_state(project_root)) {
        if (std::optional<std::string> resolved = resolve_scene_candidate(
                project_root,
                *last_scene,
                "last_scene",
                false
            )) {
            return *resolved;
        }
    }

    if (std::optional<std::string> first_scene = find_first_project_scene(project_root)) {
        return *first_scene;
    }
    throw std::runtime_error("could not find a .scene file in project: " + project_root.string());
}

fs::path resolve_profiles_path(const RunnerOptions& options, const fs::path& project_root) {
    if (!options.profiles_path.empty()) {
        fs::path path = options.profiles_path;
        if (!path.is_absolute()) {
            path = fs::current_path() / path;
        }
        return fs::absolute(path);
    }
    return project_root / kDefaultProfilePath;
}

std::string required_request_string(const nos::trent& object, const char* key) {
    const nos::trent* value = object._get(key);
    if (value == nullptr || !value->is_string() || value->as_string().empty()) {
        throw std::runtime_error(
            std::string("resolved build request field must be a non-empty string: ") + key
        );
    }
    return value->as_string();
}

BuildProfile resolve_profile_request(
    const fs::path& project_root,
    const fs::path& profiles_path,
    const std::string& profile_name
) {
    configure_python_backend_environment();
    const auto nonce = std::chrono::high_resolution_clock::now().time_since_epoch().count();
    const fs::path request_path = fs::temp_directory_path()
        / ("termin-profile-request-" + std::to_string(nonce) + ".json");
    const std::vector<std::string> command = {
        "termin_builder",
        "resolve",
        profile_name,
        "--project",
        project_root.string(),
        "--profiles",
        profiles_path.string(),
        "--request-output",
        request_path.string(),
    };
    const int resolve_code = run_process(command);
    if (resolve_code != 0) {
        std::error_code remove_ec;
        fs::remove(request_path, remove_ec);
        throw std::runtime_error(
            "failed to resolve build profile '" + profile_name
            + "' through the canonical profile backend"
        );
    }

    try {
        nos::trent request = nos::json::parse_file(request_path.string());
        std::error_code remove_ec;
        fs::remove(request_path, remove_ec);
        if (!request.is_dict()) {
            throw std::runtime_error("resolved build request root must be a JSON object");
        }
        return BuildProfile{
            required_request_string(request, "profile"),
            required_request_string(request, "target"),
            required_request_string(request, "entry_scene"),
            required_request_string(request, "output_dir"),
        };
    } catch (...) {
        std::error_code remove_ec;
        fs::remove(request_path, remove_ec);
        throw;
    }
}

fs::path resolve_output_dir(const fs::path& project_root, const BuildProfile& profile) {
    fs::path output_dir = profile.output_dir;
    if (!output_dir.is_absolute()) {
        output_dir = project_root / output_dir;
    }
    return output_dir;
}

std::optional<fs::path> read_bundle_launcher_path(
    const fs::path& output_dir,
    const fs::path& app_manifest_path
) {
    std::error_code ec;
    if (!fs::exists(app_manifest_path, ec)) {
        return std::nullopt;
    }

    nos::trent manifest = nos::json::parse_file(app_manifest_path.string());
    if (!manifest.is_dict()) {
        throw std::runtime_error("app manifest root must be a JSON object: " + app_manifest_path.string());
    }

    const nos::trent* runtime = manifest._get("runtime");
    if (runtime == nullptr || runtime->is_nil()) {
        return std::nullopt;
    }
    if (!runtime->is_dict()) {
        throw std::runtime_error("app manifest field 'runtime' must be a JSON object: " + app_manifest_path.string());
    }

    const nos::trent* launcher = runtime->_get("launcher");
    if (launcher == nullptr || launcher->is_nil()) {
        return std::nullopt;
    }
    if (!launcher->is_string()) {
        throw std::runtime_error("app manifest field 'runtime.launcher' must be a string: " + app_manifest_path.string());
    }

    fs::path launcher_path = launcher->as_string();
    if (launcher_path.empty()) {
        return std::nullopt;
    }
    if (!launcher_path.is_absolute()) {
        launcher_path = output_dir / launcher_path;
    }
    return launcher_path;
}

std::vector<fs::path> packaged_launcher_candidates(
    const fs::path& output_dir,
    const fs::path& app_manifest_path
) {
    std::vector<fs::path> candidates;
    if (std::optional<fs::path> manifest_launcher = read_bundle_launcher_path(output_dir, app_manifest_path)) {
        candidates.push_back(*manifest_launcher);
    }

#ifdef _WIN32
    candidates.push_back(output_dir / (output_dir.filename().string() + ".exe"));
#else
    candidates.push_back(output_dir / output_dir.filename());
#endif
    candidates.push_back(output_dir / "bin" / "termin_player");
#ifdef _WIN32
    candidates.push_back(output_dir / "bin" / "termin_player.exe");
#endif
    return candidates;
}

std::optional<fs::path> resolve_packaged_launcher(
    const fs::path& output_dir,
    const fs::path& app_manifest_path
) {
    std::error_code ec;
    for (const fs::path& candidate : packaged_launcher_candidates(output_dir, app_manifest_path)) {
        if (fs::exists(candidate, ec) && fs::is_regular_file(candidate, ec)) {
            return candidate;
        }
    }
    return std::nullopt;
}

void print_command(const std::vector<std::string>& command) {
    for (std::size_t i = 0; i < command.size(); ++i) {
        if (i != 0) {
            std::cout << ' ';
        }
        std::cout << command[i];
    }
    std::cout << "\n";
}

int maybe_build_profile(
    const ParsedArgs& args,
    const fs::path& project_root,
    const fs::path& profiles_path,
    bool build_output_missing
) {
    if (!args.options.rebuild && !build_output_missing) {
        return 0;
    }

    if (!args.options.rebuild && !args.options.build_if_missing) {
        std::cerr
            << "termin_runner: build output does not exist for profile '" << args.profile_name << "'.\n"
            << "Run 'termin build " << args.profile_name
            << " --project " << project_root.string()
            << "' or pass --build-if-missing.\n";
        return 4;
    }

    std::vector<std::string> build_command = {
        "termin_builder",
        "build",
        args.profile_name,
        "--project",
        project_root.string(),
        "--profiles",
        profiles_path.string(),
    };

    if (args.options.dry_run) {
        std::cout << "Build command: ";
        print_command(build_command);
        return 0;
    }

    std::cout << "Executing build profile before run...\n";
    return run_process(build_command);
}

std::vector<std::string> python_module_command() {
    return termin_cli::python_backend::python_module_command("termin.player");
}

int command_run(const ParsedArgs& args) {
    fs::path project_root = find_project_root(args.options.project_root);
    fs::path profiles_path = resolve_profiles_path(args.options, project_root);
    BuildProfile profile = resolve_profile_request(project_root, profiles_path, args.profile_name);
    fs::path output_dir = resolve_output_dir(project_root, profile);
    fs::path app_manifest_path = output_dir / "app.json";
    fs::path package_manifest_path = output_dir / "package" / "manifest.json";

    std::cout
        << "Profile: " << profile.name << "\n"
        << "Project: " << project_root << "\n"
        << "Profiles: " << profiles_path << "\n"
        << "Run mode: " << args.options.mode << "\n"
        << "Target: " << profile.target << "\n"
        << "Entry scene: " << profile.entry_scene << "\n"
        << "Output dir: " << profile.output_dir << "\n"
        << std::flush;

    if (profile.target != "desktop" && args.options.mode == "build") {
        std::cerr
            << "termin_runner: unsupported build run target '"
            << profile.target << "'.\n";
        return 3;
    }

    configure_python_backend_environment();
    if (args.options.backend.has_value()) {
        set_env_value("TERMIN_BACKEND", *args.options.backend);
    }

    std::vector<std::string> command = python_module_command();
    if (args.options.mode == "build") {
        const bool has_desktop_bundle = fs::exists(app_manifest_path) && fs::exists(package_manifest_path);
        int build_code = maybe_build_profile(
            args,
            project_root,
            profiles_path,
            !has_desktop_bundle
        );
        if (build_code != 0) {
            return build_code;
        }
        const bool has_bundle_after_build = fs::exists(app_manifest_path) && fs::exists(package_manifest_path);
        if (has_bundle_after_build) {
            std::optional<fs::path> player_path = resolve_packaged_launcher(output_dir, app_manifest_path);
            if (!player_path.has_value()) {
                std::cerr
                    << "termin_runner: packaged desktop bundle player does not exist: "
                    << app_manifest_path << "\n"
                    << "Rebuild the profile with a Termin SDK that writes the bundle launcher.\n";
                return 5;
            }
            command.clear();
            command.emplace_back(player_path->string());
        }
        if (!has_bundle_after_build) {
            std::cerr
                << "termin_runner: packaged desktop bundle does not exist: "
                << app_manifest_path << "\n"
                << "Run 'termin build " << args.profile_name
                << " --project " << project_root.string()
                << "' to create a packaged build.\n";
            return 4;
        }
    } else {
        command.emplace_back(project_root.string());
        command.emplace_back("--scene");
        command.emplace_back(args.options.scene_override.value_or(profile.entry_scene));
    }

    command.insert(command.end(), args.options.player_args.begin(), args.options.player_args.end());

    std::cout << "Player command: ";
    print_command(command);
    if (args.options.dry_run) {
        std::cout << "Dry run: player execution skipped.\n";
        return 0;
    }
    return run_process(command);
}

int command_play(const ParsedArgs& args) {
    fs::path project_root = find_project_root(args.options.project_root);
    std::string scene_name = resolve_play_scene(project_root, args);

    std::cout
        << "Project: " << project_root << "\n"
        << "Run mode: play\n"
        << "Entry scene: " << scene_name << "\n"
        << std::flush;

    configure_python_backend_environment();
    if (args.options.backend.has_value()) {
        set_env_value("TERMIN_BACKEND", *args.options.backend);
    }

    std::vector<std::string> command = python_module_command();
    command.emplace_back(project_root.string());
    command.emplace_back("--scene");
    command.emplace_back(scene_name);
    command.insert(command.end(), args.options.player_args.begin(), args.options.player_args.end());

    std::cout << "Player command: ";
    print_command(command);
    if (args.options.dry_run) {
        std::cout << "Dry run: player execution skipped.\n";
        return 0;
    }
    return run_process(command);
}

} // namespace

int main(int argc, char** argv) {
    try {
        ParsedArgs args = parse_args(argc, argv);
        if (args.command == "help") {
            print_help();
            return 0;
        }
        if (args.command == "run") {
            return command_run(args);
        }
        if (args.command == "play") {
            return command_play(args);
        }
        throw std::runtime_error("unknown command: " + args.command);
    } catch (const std::exception& exc) {
        std::cerr << "termin_runner: " << exc.what() << "\n";
        print_usage_error();
        return 2;
    }
}
