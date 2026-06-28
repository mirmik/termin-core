#!/usr/bin/env python3

from setuptools import setup


setup(
    name="termin-mcp",
    version="0.1.0",
    license="MIT",
    description="Shared MCP helpers for Termin runtime processes",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.10",
    packages=["termin.mcp"],
    package_dir={"termin.mcp": "termin/mcp"},
    install_requires=[
        "tcbase",
        "termin-assets",
        "termin-scene",
        "numpy",
        "Pillow",
    ],
    zip_safe=False,
)
