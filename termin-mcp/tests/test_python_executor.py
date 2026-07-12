import threading
import time

from termin.mcp.python_executor import PythonScriptExecutor


def test_repl_blank_line_completes_buffered_multiline_statement():
    executor = PythonScriptExecutor(lambda: {})

    assert executor.execute_repl_line("for i in range(2):").wants_more
    assert executor.execute_repl_line("    print(i)").wants_more
    result = executor.execute_repl_line("")

    assert result.ok
    assert not result.wants_more
    assert result.output == "0\n1\n"


def test_timed_out_queued_request_is_cancelled_before_main_thread_poll() -> None:
    events: list[str] = []
    executor = PythonScriptExecutor(lambda: {"events": events})
    result_holder = []

    worker = threading.Thread(
        target=lambda: result_holder.append(
            executor.execute_script_from_any_thread("events.append('late')", timeout=0.01)
        )
    )
    worker.start()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert result_holder[0].error == "Timed out waiting for main thread"
    assert executor.process_pending() == 0
    assert events == []


def test_main_thread_claim_wins_timeout_race_and_returns_completed_result() -> None:
    started = threading.Event()
    release = threading.Event()
    executor = PythonScriptExecutor(lambda: {"started": started, "release": release})
    result_holder = []

    worker = threading.Thread(
        target=lambda: result_holder.append(
            executor.execute_script_from_any_thread(
                "started.set()\nrelease.wait()\nprint('completed')",
                timeout=0.01,
            )
        )
    )
    worker.start()

    def release_after_claim() -> None:
        assert started.wait(timeout=1.0)
        time.sleep(0.05)
        release.set()

    releaser = threading.Thread(target=release_after_claim)
    releaser.start()
    assert executor.process_pending() == 1
    worker.join(timeout=1.0)
    releaser.join(timeout=1.0)

    assert not worker.is_alive()
    assert result_holder[0].ok
    assert result_holder[0].output == "completed\n"
