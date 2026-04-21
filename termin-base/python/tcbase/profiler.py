"""
Иерархический профайлер, живущий в termin-base.

Делегирует к C ядру (TcProfiler) через биндинг в ``_tcbase_native.profiler``.
Доступен любому модулю, линкующемуся на tcbase — в том числе tcgui, которому
не нужно подтягивать termin-app ради профайлинга.

Пример:
    from tcbase.profiler import Profiler

    profiler = Profiler.instance()
    profiler.enabled = True

    with profiler.section("Work"):
        do_work()
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Iterator, NamedTuple

from tcbase._tcbase_native import profiler as _profiler_mod

TcProfiler = _profiler_mod.TcProfiler


class SectionStats(NamedTuple):
    cpu_ms: float
    children_ms: float
    call_count: int


@dataclass
class SectionTiming:
    name: str
    cpu_ms: float = 0.0
    children_ms: float = 0.0
    call_count: int = 0
    children: Dict[str, "SectionTiming"] = field(default_factory=dict)


@dataclass
class FrameProfile:
    frame_number: int
    total_ms: float = 0.0
    sections: Dict[str, SectionTiming] = field(default_factory=dict)


class Profiler:
    """Иерархический профайлер, singleton поверх TcProfiler."""

    _instance: "Profiler | None" = None

    @classmethod
    def instance(cls) -> "Profiler":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, history_size: int = 120):
        self._tc = TcProfiler.instance()
        self._history_size = history_size

    @property
    def _current_frame(self):
        return self._tc.current_frame

    @property
    def enabled(self) -> bool:
        return self._tc.enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._tc.enabled = value

    @property
    def detailed_rendering(self) -> bool:
        return self._tc.detailed_rendering

    @detailed_rendering.setter
    def detailed_rendering(self, value: bool) -> None:
        self._tc.detailed_rendering = value

    @property
    def history(self) -> List[FrameProfile]:
        return self._convert_history()

    def clear_history(self) -> None:
        self._tc.clear_history()

    def begin_frame(self) -> None:
        self._tc.begin_frame()

    def end_frame(self) -> None:
        self._tc.end_frame()

    @contextmanager
    def section(self, name: str) -> Iterator[None]:
        if not self._tc.enabled:
            yield
            return
        self._tc.begin_section(name)
        try:
            yield
        finally:
            self._tc.end_section()

    def _convert_history(self) -> List[FrameProfile]:
        result = []
        for c_frame in self._tc.history:
            frame = FrameProfile(
                frame_number=c_frame.frame_number,
                total_ms=c_frame.total_ms,
            )
            self._build_sections(c_frame.sections, frame.sections)
            result.append(frame)
        return result

    def _build_sections(self, c_sections: list, out: Dict[str, SectionTiming],
                        parent_idx: int = -1) -> None:
        for i, s in enumerate(c_sections):
            if s.parent_index == parent_idx:
                timing = SectionTiming(
                    name=s.name,
                    cpu_ms=s.cpu_ms,
                    children_ms=s.children_ms,
                    call_count=s.call_count,
                )
                out[s.name] = timing
                self._build_sections(c_sections, timing.children, i)

    def last_frame(self) -> FrameProfile | None:
        history = self._convert_history()
        return history[-1] if history else None

    def average(self, frames: int = 60) -> Dict[str, float]:
        detailed = self.detailed_average(frames)
        return {name: stats.cpu_ms for name, stats in detailed.items()}

    def detailed_average(self, frames: int = 60) -> Dict[str, SectionStats]:
        history = self._convert_history()
        if not history:
            return {}
        recent = history[-frames:]
        totals: Dict[str, List[tuple]] = {}

        def collect(sections: Dict[str, SectionTiming], prefix: str = "") -> None:
            for name, timing in sections.items():
                full_path = f"{prefix}{name}" if prefix else name
                totals.setdefault(full_path, []).append(
                    (timing.cpu_ms, timing.children_ms, timing.call_count))
                collect(timing.children, f"{full_path}/")

        for frame in recent:
            collect(frame.sections)

        result = {}
        for name, samples in totals.items():
            avg_ms = sum(s[0] for s in samples) / len(samples)
            avg_children_ms = sum(s[1] for s in samples) / len(samples)
            avg_count = sum(s[2] for s in samples) / len(samples)
            result[name] = SectionStats(
                cpu_ms=avg_ms, children_ms=avg_children_ms,
                call_count=round(avg_count))
        return result

    def print_report(self, frames: int = 60) -> None:
        detailed = self.detailed_average(frames)
        if not detailed:
            print("No profiling data")
            return

        history = self._convert_history()
        sorted_sections = sorted(
            detailed.items(), key=lambda x: (x[0].count("/"), -x[1].cpu_ms))
        total = sum(stats.cpu_ms for name, stats in sorted_sections if "/" not in name)

        print(f"\n=== Profiler Report (avg {min(frames, len(history))} frames) ===")
        if total > 0:
            print(f"Total: {total:.2f}ms ({1000/total:.0f} FPS)")
        print()

        for name, stats in sorted_sections:
            indent = "  " * name.count("/")
            base_name = name.split("/")[-1]
            pct = (stats.cpu_ms / total * 100) if total > 0 else 0
            bar = "█" * int(pct / 5)
            count_str = f"x{stats.call_count}" if stats.call_count > 1 else ""
            print(f"{indent}{base_name:20} {stats.cpu_ms:6.2f}ms {pct:5.1f}% {count_str:>5} {bar}")

        print()
