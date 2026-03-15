#!/usr/bin/env python3

from setuptools import setup, Extension
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt


import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_tcbase_native", "_geom_native"]
    source_dir = _DIR


setup(
    name="tcbase",
    version="0.1.0",
    license="MIT",
    description="Base types shared between termin libraries",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["tcbase"],
    package_dir={"tcbase": "python/tcbase"},
    package_data={
        "tcbase": [
            "include/**/*.h",
            "include/**/*.hpp",
            "lib/*.so*",
            "*.dll",
            "lib/*.dll",
            "lib/*.lib",
            "lib/cmake/termin_base/*.cmake",
        ],
    },
    ext_modules=[
        Extension("tcbase._tcbase_native", sources=[]),
        Extension("tcbase._geom_native", sources=[]),
    ],
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
