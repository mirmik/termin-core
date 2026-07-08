#pragma once

#include <ostream>
#include <string>

#include <tcbase/tc_trent.hpp>
#include <tcbase/tc_value_trent.hpp>
#include <tcbase/trent/yaml.h>

namespace tc::yaml {

inline trent parse(const char* text) {
    return trent::adopt(trent_to_tc_value(nos::yaml::parse(text)));
}

inline trent parse(const std::string& text) {
    return trent::adopt(trent_to_tc_value(nos::yaml::parse(text)));
}

inline trent parse_file(const std::string& path) {
    return trent::adopt(trent_to_tc_value(nos::yaml::parse_file(path)));
}

inline std::string to_string(trent_view value) {
    return nos::yaml::to_string(tc_value_to_trent(*value.raw()));
}

inline std::string to_string(const trent& value) {
    return to_string(value.view());
}

inline void print_to(trent_view value, std::ostream& os) {
    nos::yaml::print_to(tc_value_to_trent(*value.raw()), os);
}

inline void print_to(const trent& value, std::ostream& os) {
    print_to(value.view(), os);
}

} // namespace tc::yaml
