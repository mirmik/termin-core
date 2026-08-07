#include "termin_python_backend.hpp"

#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    try {
        termin_cli::python_backend::configure_environment();
        std::vector<std::string> command = termin_cli::python_backend::python_module_command("termin.project.init_cli");
        for (int index = 1; index < argc; ++index) {
            command.emplace_back(argv[index]);
        }
        return termin_cli::python_backend::run_process(command, "project init backend");
    } catch (const std::exception& exc) {
        std::cerr << "termin_init: " << exc.what() << "\n";
        return 2;
    }
}
