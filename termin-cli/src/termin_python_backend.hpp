#pragma once

#include <filesystem>
#include <optional>
#include <string>
#include <vector>

namespace termin_cli::python_backend {

namespace fs = std::filesystem;

fs::path executable_dir();
std::string env_path_separator();
std::string current_env(const char* name);
void set_env_value(const char* name, const std::string& value);
void prepend_env_path(const char* name, const fs::path& value);
void append_python_prefix_paths(std::vector<fs::path>& paths, const fs::path& prefix_root);
std::vector<fs::path> python_module_paths(const fs::path& install_root, const fs::path& exe_dir);
void configure_environment();
std::optional<fs::path> bundled_python_executable(const fs::path& install_root);
std::vector<std::string> python_module_command(const std::string& module_name);
int run_process(const std::vector<std::string>& args, const char* process_label);

} // namespace termin_cli::python_backend
