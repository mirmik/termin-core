#!/usr/bin/env python3

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    module_names = []
    source_dir = _DIR
    bundle_libs = True

    def build_extension(self, ext):
        # No native Python modules — just run cmake build/install to get libnanobind.so
        self._ensure_cmake_build()
        # Bundle libs into the package directory
        import pathlib
        pkg_dir = pathlib.Path(self.build_lib) / "termin_nanobind"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        self._bundle_to_dir(self._staging_dir, pkg_dir)


# Dummy extension to trigger build_ext
from setuptools import Extension

setup(
    name="termin-nanobind",
    version="0.1.0",
    license="MIT",
    description="Shared nanobind runtime library for termin packages",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin_nanobind"],
    package_dir={"termin_nanobind": "python/termin_nanobind"},
    install_requires=["nanobind"],
    package_data={
        "termin_nanobind": [
            "lib/*.so*",
            "*.dll",
            "lib/*.dll",
            "lib/*.lib",
        ],
    },
    ext_modules=[
        Extension("termin_nanobind._dummy", sources=[]),
    ],
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
