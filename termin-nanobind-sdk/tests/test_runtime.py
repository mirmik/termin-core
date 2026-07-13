from __future__ import annotations

import os

from termin_nanobind import runtime


class _DllDirectoryHandle:
    def __init__(self, path: str) -> None:
        self.path = path
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_windows_dll_directory_handles_are_retained_idempotently_and_can_close(tmp_path, monkeypatch) -> None:
    local_dir = tmp_path / "package" / "lib"
    sdk_bin = tmp_path / "sdk" / "bin"
    sdk_lib = tmp_path / "sdk" / "lib"
    for directory in (local_dir, sdk_bin, sdk_lib):
        directory.mkdir(parents=True)

    calls: list[str] = []
    handles: list[_DllDirectoryHandle] = []

    def add_dll_directory(path: str) -> _DllDirectoryHandle:
        calls.append(path)
        handle = _DllDirectoryHandle(path)
        handles.append(handle)
        return handle

    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.setattr(runtime, "_caller_lib_dirs", lambda: [local_dir, local_dir])
    monkeypatch.setattr(runtime, "find_sdk", lambda: tmp_path / "sdk")
    monkeypatch.setattr(runtime.os, "add_dll_directory", add_dll_directory, raising=False)
    monkeypatch.setattr(runtime, "_windows_dll_directory_handles", {})

    runtime.preload_sdk_libs("termin_base")
    runtime.preload_sdk_libs("termin_base")

    expected = [
        os.path.normcase(os.path.normpath(os.path.abspath(directory)))
        for directory in (local_dir, sdk_bin, sdk_lib)
    ]
    assert calls == expected
    assert set(runtime._windows_dll_directory_handles) == set(expected)
    assert all(not handle.closed for handle in handles)

    runtime.close_windows_dll_directories()

    assert runtime._windows_dll_directory_handles == {}
    assert all(handle.closed for handle in handles)
