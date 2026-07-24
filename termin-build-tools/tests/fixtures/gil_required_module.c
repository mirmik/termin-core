#define PY_SSIZE_T_CLEAN
#include <Python.h>

static struct PyModuleDef module_definition = {
    PyModuleDef_HEAD_INIT,
    "_termin_gil_required_fixture",
    "Test extension that deliberately omits Py_mod_gil.",
    -1,
    NULL,
};

PyMODINIT_FUNC PyInit__termin_gil_required_fixture(void) {
    return PyModule_Create(&module_definition);
}
