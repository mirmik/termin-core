from termin.mcp.python_executor import PythonScriptExecutor


def test_repl_blank_line_completes_buffered_multiline_statement():
    executor = PythonScriptExecutor(lambda: {})

    assert executor.execute_repl_line("for i in range(2):").wants_more
    assert executor.execute_repl_line("    print(i)").wants_more
    result = executor.execute_repl_line("")

    assert result.ok
    assert not result.wants_more
    assert result.output == "0\n1\n"
