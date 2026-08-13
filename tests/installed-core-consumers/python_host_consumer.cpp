#include <termin/python_host/python_host.hpp>

#include <filesystem>
#include <iostream>

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: core_python_host_consumer <relocated-sdk>\n";
        return 1;
    }

    termin::python_host::Config config;
    config.host_name = "Termin Core installed consumer";
    config.home = std::filesystem::absolute(argv[1]);
    config.argv = {"core_python_host_consumer"};
    const auto initialized = termin::python_host::initialize(config);
    if (!initialized.ok) {
        std::cerr << initialized.error << '\n';
        return initialized.exit_requested ? initialized.exit_code : 2;
    }

    const auto expected = termin::python_host::expected_abi();
    const auto runtime = termin::python_host::runtime_abi();
    const bool compatible = runtime.version == expected.version
        && runtime.soabi == expected.soabi
        && runtime.free_threaded
        && expected.free_threaded;
    const int finalize_result = termin::python_host::finalize();
    if (!compatible) {
        std::cerr << "embedded runtime ABI mismatch: expected "
                  << expected.describe() << ", got " << runtime.describe() << '\n';
        return 3;
    }
    return finalize_result;
}
