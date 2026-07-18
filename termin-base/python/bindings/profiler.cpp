// profiler.cpp - Python bindings for tc_profiler (base-level, no termin dep)
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <stdexcept>
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
    double start_time_ms;
    double interval_ms;
    double active_ms;
    double total_ms;
    double target_interval_ms;
    double deadline_lateness_ms;
    int missed_intervals;
    bool sections_profiled;
    std::vector<PySectionTiming> sections;
};

struct PyHistoryBatch {
    std::vector<PyFrameProfile> frames;
    int dropped_count;
    int oldest_frame_number;
    int newest_frame_number;
};

static PyFrameProfile convert_frame(const tc_frame_profile* frame) {
    PyFrameProfile result;
    result.frame_number = frame->frame_number;
    result.start_time_ms = frame->start_time_ms;
    result.interval_ms = frame->interval_ms;
    result.active_ms = frame->active_ms;
    result.total_ms = frame->total_ms;
    result.target_interval_ms = frame->target_interval_ms;
    result.deadline_lateness_ms = frame->deadline_lateness_ms;
    result.missed_intervals = frame->missed_intervals;
    result.sections_profiled = frame->sections_profiled;

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

    void begin_frame() { tc_profiler_begin_frame(); }
    void begin_frame_with_info(
        double start_time_ms,
        double interval_ms,
        double target_interval_ms,
        double deadline_lateness_ms,
        int missed_intervals
    ) {
        const tc_profiler_frame_info info{
            start_time_ms,
            interval_ms,
            target_interval_ms,
            deadline_lateness_ms,
            missed_intervals,
        };
        tc_profiler_begin_frame_with_info(&info);
    }
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

    PyHistoryBatch history_after(int last_frame_number) {
        tc_profiler_history_range range{};
        if (!tc_profiler_history_after(last_frame_number, &range)) {
            throw std::runtime_error("failed to read profiler history range");
        }
        PyHistoryBatch result;
        result.dropped_count = range.dropped_count;
        result.oldest_frame_number = range.oldest_frame_number;
        result.newest_frame_number = range.newest_frame_number;
        result.frames.reserve(static_cast<size_t>(range.count));
        for (int offset = 0; offset < range.count; ++offset) {
            tc_frame_profile* frame = tc_profiler_history_at(range.first_index + offset);
            if (!frame) {
                throw std::runtime_error("profiler history changed during range copy");
            }
            result.frames.push_back(convert_frame(frame));
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
        .def_ro("start_time_ms", &PyFrameProfile::start_time_ms)
        .def_ro("interval_ms", &PyFrameProfile::interval_ms)
        .def_ro("active_ms", &PyFrameProfile::active_ms)
        .def_ro("total_ms", &PyFrameProfile::total_ms)
        .def_ro("target_interval_ms", &PyFrameProfile::target_interval_ms)
        .def_ro("deadline_lateness_ms", &PyFrameProfile::deadline_lateness_ms)
        .def_ro("missed_intervals", &PyFrameProfile::missed_intervals)
        .def_ro("sections_profiled", &PyFrameProfile::sections_profiled)
        .def_ro("sections", &PyFrameProfile::sections)
        ;

    nb::class_<PyHistoryBatch>(m, "HistoryBatch")
        .def_ro("frames", &PyHistoryBatch::frames)
        .def_ro("dropped_count", &PyHistoryBatch::dropped_count)
        .def_ro("oldest_frame_number", &PyHistoryBatch::oldest_frame_number)
        .def_ro("newest_frame_number", &PyHistoryBatch::newest_frame_number)
        ;

    nb::class_<TcProfiler>(m, "TcProfiler")
        .def_static("instance", &TcProfiler::instance, nb::rv_policy::reference)
        .def_prop_rw("enabled", &TcProfiler::enabled, &TcProfiler::set_enabled)
        .def("begin_frame", &TcProfiler::begin_frame)
        .def("begin_frame_with_info", &TcProfiler::begin_frame_with_info,
             nb::arg("start_time_ms"), nb::arg("interval_ms"),
             nb::arg("target_interval_ms"), nb::arg("deadline_lateness_ms"),
             nb::arg("missed_intervals"))
        .def("end_frame", &TcProfiler::end_frame)
        .def("begin_section", &TcProfiler::begin_section, nb::arg("name"))
        .def("begin_section_muted", &TcProfiler::begin_section_muted, nb::arg("name"))
        .def("end_section", &TcProfiler::end_section)
        .def_prop_ro("frame_count", &TcProfiler::frame_count)
        .def_prop_ro("history_count", &TcProfiler::history_count)
        .def("history_at", &TcProfiler::history_at, nb::arg("index"))
        .def_prop_ro("history", &TcProfiler::history)
        .def("history_after", &TcProfiler::history_after, nb::arg("last_frame_number"))
        .def("clear_history", &TcProfiler::clear_history)
        .def_prop_ro("current_frame", &TcProfiler::current_frame)
        ;
}
