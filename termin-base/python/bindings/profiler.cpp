// profiler.cpp - Python bindings for tc_profiler (base-level, no termin dep)
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include "tc_profiler.h"

namespace nb = nanobind;

namespace {

struct PySectionTiming {
    std::string name;
    double cpu_ms;
    double children_ms;
    int call_count;
    int parent_index;
    int first_child;
    int next_sibling;
};

struct PyFrameProfile {
    int frame_number;
    double total_ms;
    std::vector<PySectionTiming> sections;
};

static PyFrameProfile convert_frame(const tc_frame_profile* frame) {
    PyFrameProfile result;
    result.frame_number = frame->frame_number;
    result.total_ms = frame->total_ms;

    for (int i = 0; i < frame->section_count; i++) {
        const tc_section_timing* s = &frame->sections[i];
        PySectionTiming ps;
        ps.name = s->name;
        ps.cpu_ms = s->cpu_ms;
        ps.children_ms = s->children_ms;
        ps.call_count = s->call_count;
        ps.parent_index = s->parent_index;
        ps.first_child = s->first_child;
        ps.next_sibling = s->next_sibling;
        result.sections.push_back(ps);
    }

    return result;
}

class TcProfiler {
public:
    static TcProfiler& instance() {
        static TcProfiler inst;
        return inst;
    }

    bool enabled() const { return tc_profiler_enabled(); }
    void set_enabled(bool v) { tc_profiler_set_enabled(v); }

    bool profile_components() const { return tc_profiler_profile_components(); }
    void set_profile_components(bool v) { tc_profiler_set_profile_components(v); }

    bool detailed_rendering() const { return tc_profiler_detailed_rendering(); }
    void set_detailed_rendering(bool v) { tc_profiler_set_detailed_rendering(v); }

    void begin_frame() { tc_profiler_begin_frame(); }
    void end_frame() { tc_profiler_end_frame(); }

    void begin_section(const std::string& name) { tc_profiler_begin_section(name.c_str()); }
    void begin_section_muted(const std::string& name) { tc_profiler_begin_section_muted(name.c_str()); }
    void end_section() { tc_profiler_end_section(); }

    int frame_count() const { return tc_profiler_frame_count(); }

    int history_count() const { return tc_profiler_history_count(); }

    nb::object history_at(int index) {
        tc_frame_profile* frame = tc_profiler_history_at(index);
        if (!frame) return nb::none();
        return nb::cast(convert_frame(frame));
    }

    std::vector<PyFrameProfile> history() {
        std::vector<PyFrameProfile> result;
        int count = tc_profiler_history_count();
        for (int i = 0; i < count; i++) {
            tc_frame_profile* frame = tc_profiler_history_at(i);
            if (frame) {
                result.push_back(convert_frame(frame));
            }
        }
        return result;
    }

    void clear_history() { tc_profiler_clear_history(); }

    nb::object current_frame() {
        tc_frame_profile* frame = tc_profiler_current_frame();
        if (!frame) return nb::none();
        return nb::cast(convert_frame(frame));
    }

private:
    TcProfiler() = default;
};

} // namespace

void bind_profiler(nb::module_& m) {
    nb::class_<PySectionTiming>(m, "SectionTiming")
        .def_ro("name", &PySectionTiming::name)
        .def_ro("cpu_ms", &PySectionTiming::cpu_ms)
        .def_ro("children_ms", &PySectionTiming::children_ms)
        .def_ro("call_count", &PySectionTiming::call_count)
        .def_ro("parent_index", &PySectionTiming::parent_index)
        .def_ro("first_child", &PySectionTiming::first_child)
        .def_ro("next_sibling", &PySectionTiming::next_sibling)
        ;

    nb::class_<PyFrameProfile>(m, "FrameProfile")
        .def_ro("frame_number", &PyFrameProfile::frame_number)
        .def_ro("total_ms", &PyFrameProfile::total_ms)
        .def_ro("sections", &PyFrameProfile::sections)
        ;

    nb::class_<TcProfiler>(m, "TcProfiler")
        .def_static("instance", &TcProfiler::instance, nb::rv_policy::reference)
        .def_prop_rw("enabled", &TcProfiler::enabled, &TcProfiler::set_enabled)
        .def_prop_rw("profile_components", &TcProfiler::profile_components, &TcProfiler::set_profile_components)
        .def_prop_rw("detailed_rendering", &TcProfiler::detailed_rendering, &TcProfiler::set_detailed_rendering)
        .def("begin_frame", &TcProfiler::begin_frame)
        .def("end_frame", &TcProfiler::end_frame)
        .def("begin_section", &TcProfiler::begin_section, nb::arg("name"))
        .def("begin_section_muted", &TcProfiler::begin_section_muted, nb::arg("name"))
        .def("end_section", &TcProfiler::end_section)
        .def_prop_ro("frame_count", &TcProfiler::frame_count)
        .def_prop_ro("history_count", &TcProfiler::history_count)
        .def("history_at", &TcProfiler::history_at, nb::arg("index"))
        .def_prop_ro("history", &TcProfiler::history)
        .def("clear_history", &TcProfiler::clear_history)
        .def_prop_ro("current_frame", &TcProfiler::current_frame)
        ;
}
