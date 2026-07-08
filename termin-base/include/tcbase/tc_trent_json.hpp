#pragma once

#include <string>

#include <tcbase/tc_trent.hpp>
#include <tcbase/tc_value_trent.hpp>
#include <tcbase/trent/json.h>

namespace tc::json {

inline trent parse(const char* text) {
    return trent::adopt(trent_to_tc_value(nos::json::parse(text)));
}

inline trent parse(const std::string& text) {
    return trent::adopt(trent_to_tc_value(nos::json::parse(text)));
}

inline trent parse_file(const std::string& path) {
    return trent::adopt(trent_to_tc_value(nos::json::parse_file(path)));
}

inline std::string dump(trent_view value, int indent = -1) {
    return nos::json::dump(tc_value_to_trent(*value.raw()), indent);
}

inline std::string dump(const trent& value, int indent = -1) {
    return dump(value.view(), indent);
}

} // namespace tc::json
