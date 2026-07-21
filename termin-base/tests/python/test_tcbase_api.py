from pathlib import Path

import tcbase


def test_input_enums_match_event_integer_values():
    assert tcbase.Action.PRESS.value == 1
    assert tcbase.Action.RELEASE.value == 0
    assert tcbase.MouseButton.NONE.value == -1
    assert tcbase.MouseButton.LEFT.value == 0
    assert tcbase.MouseButton.RIGHT.value == 1
    assert tcbase.MouseButton.MIDDLE.value == 2
    assert tcbase.MouseButton.OTHER.value == 3
    assert tcbase.Mods.SHIFT.value != 0
    assert tcbase.Key.A.value == 65
    assert int(tcbase.Action.PRESS) == 1
    assert int(tcbase.MouseButton.LEFT) == 0
    assert tcbase.Action.PRESS == tcbase.Action.PRESS.value
    assert tcbase.MouseButton.LEFT == tcbase.MouseButton.LEFT.value
    assert tcbase.Mods.SHIFT == tcbase.Mods.SHIFT.value


def test_settings_roundtrip_with_groups(tmp_path: Path):
    settings_path = tmp_path / "settings.json"
    s = tcbase.Settings(str(settings_path), True)

    s.set("value", 42)
    s.begin_group("ui")
    s.set("theme", "dark")
    s.set("width", 1280)
    s.end_group()
    s.save()

    s2 = tcbase.Settings(str(settings_path), True)
    s2.load()

    assert s2.get("value", None) == 42
    assert s2.get("ui/theme", None) == "dark"
    assert s2.get("ui/width", None) == 1280
    assert s2.contains("ui/theme")


def test_intern_string_diagnostics_api():
    stats = tcbase.intern_string_get_stats()
    assert set(stats) == {
        "entry_count",
        "bucket_count",
        "non_empty_bucket_count",
        "max_bucket_depth",
        "load_factor",
    }
    assert stats["entry_count"] >= 0
    assert stats["bucket_count"] >= 0

    rows = tcbase.intern_string_get_all_info()
    assert isinstance(rows, list)
    if rows:
        row = rows[0]
        assert {"string", "bucket", "depth"} <= set(row)
