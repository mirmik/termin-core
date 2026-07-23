import gc
import os
import subprocess
import threading
import weakref
from pathlib import Path

import pytest

from termin.dispatch import Dispatcher


def test_fifo_limit_cancel_and_nested_batch():
    dispatcher = Dispatcher()
    events = []

    cancelled = dispatcher.defer(lambda: events.append("cancelled"))
    assert cancelled.cancel()
    assert not cancelled.cancel()

    dispatcher.defer(
        lambda: (
            events.append("outer"),
            dispatcher.defer(lambda: events.append("nested")),
        )
    )
    dispatcher.defer(lambda: events.append("second"))

    first = dispatcher.run_pending()
    assert first.executed == 2
    assert first.remaining == 1
    assert events == ["outer", "second"]

    second = dispatcher.run_pending()
    assert second.executed == 1
    assert second.remaining == 0
    assert events == ["outer", "second", "nested"]


def test_callbacks_run_on_the_drain_caller():
    dispatcher = Dispatcher()
    callback_thread = []
    drain_thread = []
    dispatcher.defer(lambda: callback_thread.append(threading.get_ident()))

    def drain():
        drain_thread.append(threading.get_ident())
        dispatcher.run_pending()

    worker = threading.Thread(target=drain)
    worker.start()
    worker.join()
    assert callback_thread == drain_thread


def test_worker_can_post_for_another_thread_to_drain():
    dispatcher = Dispatcher()
    events = []

    worker = threading.Thread(
        target=lambda: dispatcher.defer(lambda: events.append("done"))
    )
    worker.start()
    worker.join()

    assert dispatcher.pending_count == 1
    dispatcher.run_pending()
    assert events == ["done"]


def test_exception_is_reported_and_does_not_stop_batch(capsys):
    dispatcher = Dispatcher()
    events = []

    def fail():
        raise ValueError("expected deferred failure")

    dispatcher.defer(fail)
    dispatcher.defer(lambda: events.append("after"))
    stats = dispatcher.run_pending()

    assert stats.executed == 2
    assert stats.failed == 1
    assert events == ["after"]
    assert "expected deferred failure" in capsys.readouterr().err


def test_close_rejects_posts_and_discard_releases_callback():
    dispatcher = Dispatcher()

    def callback():
        pass

    callback_ref = weakref.ref(callback)
    dispatcher.defer(callback)
    del callback
    gc.collect()
    assert callback_ref() is not None

    assert dispatcher.discard_pending() == 1
    gc.collect()
    assert callback_ref() is None

    assert dispatcher.close()
    assert not dispatcher.open
    with pytest.raises(RuntimeError, match="closed"):
        dispatcher.defer(lambda: None)


def test_installed_python_consumer_in_hostile_environment():
    sdk_root = Path(os.environ["TERMIN_SDK"]).resolve()
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONHOME": str(sdk_root / "__invalid_python_home__"),
            "PYTHONPATH": str(sdk_root / "__invalid_python_path__"),
            "PYTHONUSERBASE": str(sdk_root / "__invalid_user_base__"),
        }
    )
    script = """
from termin.dispatch import Dispatcher

dispatcher = Dispatcher()
events = []
dispatcher.defer(lambda: events.append("installed"))
stats = dispatcher.run_pending()
assert stats.executed == 1
assert events == ["installed"]
"""
    result = subprocess.run(
        [str(sdk_root / "bin" / "termin_python"), "-I", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr


def test_installed_c_and_cpp_consumers(tmp_path):
    sdk_root = Path(os.environ["TERMIN_SDK"]).resolve()
    source_root = Path(__file__).resolve().parents[1] / "installed_consumer"
    build_root = tmp_path / "build"

    configure = subprocess.run(
        [
            "cmake",
            "-S",
            str(source_root),
            "-B",
            str(build_root),
            f"-DCMAKE_PREFIX_PATH={sdk_root}",
            "-DCMAKE_BUILD_TYPE=Release",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert configure.returncode == 0, configure.stderr

    build = subprocess.run(
        ["cmake", "--build", str(build_root), "--parallel", "2"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr

    executable_dir = build_root / ("Release" if os.name == "nt" else "")
    executable_suffix = ".exe" if os.name == "nt" else ""
    for name in ("termin_dispatch_installed_c", "termin_dispatch_installed_cpp"):
        run = subprocess.run(
            [str(executable_dir / f"{name}{executable_suffix}")],
            check=False,
            capture_output=True,
            text=True,
        )
        assert run.returncode == 0, run.stderr
