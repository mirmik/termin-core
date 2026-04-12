#!/usr/bin/env python3

# termin-nanobind-sdk: pure-Python pip package.
#
# Ships only the `termin_nanobind` Python helpers (__init__.py + runtime.py
# for SDK discovery and library preloading). The libnanobind.so shared
# library is NOT shipped here — it is built by build-sdk-bindings.sh into
# $TERMIN_SDK/lib/libnanobind.so and resolved at runtime via preload_sdk_libs.

from setuptools import setup

setup(
    name="termin-nanobind",
    version="0.1.0",
    license="MIT",
    description="Runtime helpers for termin pip packages (SDK discovery, library preloading)",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin_nanobind"],
    package_dir={"termin_nanobind": "python/termin_nanobind"},
    install_requires=["nanobind"],
    zip_safe=False,
)
