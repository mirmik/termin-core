#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <unistd.h>
#endif

namespace {

namespace fs = std::filesystem;

struct Options {
    fs::path project_root;
    fs::path stdlib_source;
    bool clean = false;
    bool dry_run = false;
};

fs::path executable_dir() {
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

void print_help() {
    std::cout
        << "termin_stdlib - Termin standard library deployment utility\n"
        << "\n"
        << "Usage:\n"
        << "  termin_stdlib --help\n"
        << "  termin_stdlib sync [--project <dir>] [--source <dir>] [--clean] [--dry-run]\n"
        << "\n"
        << "Commands:\n"
        << "  sync      Copy SDK stdlib into <project>/stdlib. This is the default command.\n"
        << "\n"
        << "Options:\n"
        << "  --project <dir>  Project directory, or a path inside a Termin project.\n"
        << "  --source <dir>   Override SDK stdlib source directory.\n"
        << "  --clean          Remove files from project stdlib that no longer exist in SDK stdlib.\n"
        << "  --dry-run        Print planned changes without writing files.\n";
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

bool is_stdlib_root(const fs::path& path) {
    std::error_code ec;
    return fs::exists(path / "shaders", ec)
        && fs::exists(path / "materials", ec)
        && fs::is_directory(path, ec);
}

void append_existing_python_stdlib_candidates(std::vector<fs::path>& candidates, const fs::path& install_root) {
    fs::path lib_dir = install_root / "lib";
    std::error_code ec;
    if (!fs::exists(lib_dir, ec)) {
        return;
    }
    for (const fs::directory_entry& entry : fs::directory_iterator(lib_dir, ec)) {
        if (ec) {
            return;
        }
        if (!entry.is_directory(ec)) {
            continue;
        }
        const std::string name = entry.path().filename().string();
        if (name.rfind("python3.", 0) == 0) {
            candidates.push_back(entry.path() / "site-packages" / "termin" / "stdlib" / "resources");
        }
    }
}

fs::path find_stdlib_source(const fs::path& override_source) {
    if (!override_source.empty()) {
        fs::path source = fs::absolute(override_source);
        if (!is_stdlib_root(source)) {
            throw std::runtime_error("stdlib source is not a valid stdlib directory: " + source.string());
        }
        return source;
    }

    fs::path exe_dir = executable_dir();
    fs::path install_root = exe_dir.parent_path();
    std::vector<fs::path> candidates = {
        install_root / "lib" / "python" / "termin" / "stdlib" / "resources",
    };
    append_existing_python_stdlib_candidates(candidates, install_root);

    for (fs::path dir = exe_dir; !dir.empty(); dir = dir.parent_path()) {
        candidates.push_back(dir / "termin-stdlib" / "python" / "termin" / "stdlib" / "resources");
        if (dir == dir.root_path()) {
            break;
        }
    }

    for (const fs::path& candidate : candidates) {
        std::error_code ec;
        fs::path canonical = fs::weakly_canonical(candidate, ec);
        const fs::path& path = ec ? candidate : canonical;
        if (is_stdlib_root(path)) {
            return path;
        }
    }
    throw std::runtime_error("could not locate SDK stdlib directory");
}

bool same_file_content(const fs::path& left, const fs::path& right) {
    std::error_code ec;
    if (!fs::exists(left, ec) || !fs::exists(right, ec)) {
        return false;
    }
    if (fs::file_size(left, ec) != fs::file_size(right, ec)) {
        return false;
    }

    std::ifstream a(left, std::ios::binary);
    std::ifstream b(right, std::ios::binary);
    if (!a || !b) {
        return false;
    }

    constexpr std::size_t kBufferSize = 8192;
    std::vector<char> ab(kBufferSize);
    std::vector<char> bb(kBufferSize);
    while (a && b) {
        a.read(ab.data(), static_cast<std::streamsize>(ab.size()));
        b.read(bb.data(), static_cast<std::streamsize>(bb.size()));
        if (a.gcount() != b.gcount()) {
            return false;
        }
        if (!std::equal(ab.begin(), ab.begin() + a.gcount(), bb.begin())) {
            return false;
        }
    }
    return true;
}

std::vector<fs::path> collect_files(const fs::path& root) {
    std::vector<fs::path> files;
    std::error_code ec;
    if (!fs::exists(root, ec)) {
        return files;
    }
    for (const fs::directory_entry& entry : fs::recursive_directory_iterator(root, ec)) {
        if (ec) {
            throw std::runtime_error("failed to iterate directory: " + root.string());
        }
        if (entry.is_regular_file(ec)) {
            files.push_back(entry.path());
        }
    }
    std::sort(files.begin(), files.end());
    return files;
}

void remove_empty_directories(const fs::path& root) {
    std::vector<fs::path> dirs;
    std::error_code ec;
    if (!fs::exists(root, ec)) {
        return;
    }
    for (const fs::directory_entry& entry : fs::recursive_directory_iterator(root, ec)) {
        if (entry.is_directory(ec)) {
            dirs.push_back(entry.path());
        }
    }
    std::sort(dirs.rbegin(), dirs.rend());
    for (const fs::path& dir : dirs) {
        fs::remove(dir, ec);
    }
}

int command_sync(const Options& options) {
    fs::path project_root = find_project_root(options.project_root);
    fs::path source_root = find_stdlib_source(options.stdlib_source);
    fs::path target_root = project_root / "stdlib";

    std::cout << "Project: " << project_root << "\n";
    std::cout << "Source: " << source_root << "\n";
    std::cout << "Target: " << target_root << "\n";

    std::set<fs::path> source_rel_paths;
    int copied = 0;
    int updated = 0;

    for (const fs::path& source_path : collect_files(source_root)) {
        fs::path rel = fs::relative(source_path, source_root);
        source_rel_paths.insert(rel);
        fs::path target_path = target_root / rel;

        if (same_file_content(source_path, target_path)) {
            continue;
        }

        bool exists = fs::exists(target_path);
        if (options.dry_run) {
            std::cout << (exists ? "update " : "copy ") << rel.generic_string() << "\n";
        } else {
            std::error_code ec;
            fs::create_directories(target_path.parent_path(), ec);
            if (ec) {
                throw std::runtime_error("failed to create directory: " + target_path.parent_path().string());
            }
            fs::copy_file(source_path, target_path, fs::copy_options::overwrite_existing, ec);
            if (ec) {
                throw std::runtime_error("failed to copy stdlib file: " + source_path.string());
            }
        }

        if (exists) {
            ++updated;
        } else {
            ++copied;
        }
    }

    int removed = 0;
    if (options.clean) {
        for (const fs::path& target_path : collect_files(target_root)) {
            fs::path rel = fs::relative(target_path, target_root);
            if (source_rel_paths.find(rel) != source_rel_paths.end()) {
                continue;
            }
            if (options.dry_run) {
                std::cout << "remove " << rel.generic_string() << "\n";
            } else {
                std::error_code ec;
                fs::remove(target_path, ec);
                if (ec) {
                    throw std::runtime_error("failed to remove stale stdlib file: " + target_path.string());
                }
            }
            ++removed;
        }
        if (!options.dry_run) {
            remove_empty_directories(target_root);
        }
    }

    std::cout
        << "Copied: " << copied << "\n"
        << "Updated: " << updated << "\n"
        << "Removed: " << removed << "\n";
    return 0;
}

Options parse_options(int argc, char** argv) {
    Options options;
    int index = 1;
    if (index < argc) {
        const std::string first = argv[index];
        if (first == "--help" || first == "-h" || first == "help") {
            print_help();
            std::exit(0);
        }
        if (first == "sync" || first == "deploy") {
            ++index;
        } else if (!first.empty() && first[0] != '-') {
            throw std::runtime_error("unknown command: " + first);
        }
    }

    for (; index < argc; ++index) {
        std::string arg = argv[index];
        if (arg == "--help" || arg == "-h" || arg == "help") {
            print_help();
            std::exit(0);
        }

        auto take_value = [&]() -> std::string {
            if (index + 1 >= argc) {
                throw std::runtime_error("missing value for " + arg);
            }
            return argv[++index];
        };

        if (arg == "--project") {
            options.project_root = take_value();
        } else if (arg == "--source" || arg == "--stdlib-source") {
            options.stdlib_source = take_value();
        } else if (arg == "--clean") {
            options.clean = true;
        } else if (arg == "--dry-run") {
            options.dry_run = true;
        } else {
            throw std::runtime_error("unknown option: " + arg);
        }
    }
    return options;
}

} // namespace

int main(int argc, char** argv) {
    try {
        Options options = parse_options(argc, argv);
        return command_sync(options);
    } catch (const std::exception& exc) {
        std::cerr << "termin_stdlib: " << exc.what() << "\n";
        std::cerr << "Run 'termin_stdlib --help' for usage.\n";
        return 2;
    }
}
