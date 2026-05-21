// tc_kind.hpp - Unified kind registry facade for C++ and Python support.
#pragma once

#include "termin/inspect/tc_kind_cpp_ext.hpp"
#include "inspect/tc_kind_python.hpp"

namespace tc {

inline void register_builtin_kinds() {
    register_builtin_cpp_kinds();
}

} // namespace tc
