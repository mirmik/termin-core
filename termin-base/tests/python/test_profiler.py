from tcbase.profiler import Profiler


def test_profiler_last_complete_frame_excludes_open_history_slot():
    profiler = Profiler.instance()
    previous_enabled = profiler.enabled
    profiler.enabled = True
    profiler.clear_history()
    try:
        profiler.begin_frame()
        with profiler.section("First"):
            pass
        assert profiler.last_complete_frame() is None
        profiler.end_frame()

        first = profiler.last_complete_frame()
        assert first is not None
        assert list(first.sections) == ["First"]

        profiler.begin_frame()
        with profiler.section("Second"):
            pass
        assert profiler.last_complete_frame().frame_number == first.frame_number
        profiler.end_frame()
        assert profiler.last_complete_frame().frame_number == first.frame_number + 1
    finally:
        if profiler._current_frame is not None:
            profiler.end_frame()
        profiler.clear_history()
        profiler.enabled = previous_enabled
