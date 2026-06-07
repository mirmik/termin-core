#!/usr/bin/env python3

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    upstream_packages = {"tcbase": "libtermin_base", "termin_nanobind": "libnanobind"}
    bundle_includes = True
    source_dir = _DIR


setup(
    name="termin-inspect",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="Inspect/Kind system with Python bindings",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin.inspect"],
    package_dir={"termin.inspect": "python/termin/inspect"},
    install_requires=["tcbase", "termin-nanobind"],
    package_data={
        "termin.inspect": [
            "include/**/*.h",
            "include/**/*.hpp",
            "lib/*.so*",
            "lib/cmake/**/*",
            "*.dll",
            "lib/*.dll",
            "lib/*.lib",
        ],
    },
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
