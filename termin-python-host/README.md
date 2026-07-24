# termin-python-host

`termin-python-host` is the neutral C++ boundary for processes that embed
CPython. It owns:

- initialization through `PyConfig` and `Py_InitializeFromConfig`;
- isolated versus host-environment policy supplied explicitly by each host;
- `sys.argv`, Python home and program-name configuration before initialization;
- runtime ABI validation against the Python headers and SOABI used at build
  time;
- explicit finalization for lifecycle tests and short-lived smoke processes.

The library does not own engine, editor, player, module or UI state. Product
hosts remain responsible for releasing their Python callbacks and native
objects before finalizing CPython. Long-lived editor/player processes currently
leave final interpreter teardown to process exit until the process-global state
audit is complete.

Callers must not use legacy global initialization controls such as
`Py_SetPythonHome`, `PySys_SetArgvEx`, `Py_NoSiteFlag` or
`Py_IgnoreEnvironmentFlag`.
