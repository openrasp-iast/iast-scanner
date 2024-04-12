#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import setuptools

packages = [
    "iast_scanner",
    "iast_scanner.core",
    "iast_scanner.core.components",
    "iast_scanner.core.components.plugin",
    "iast_scanner.core.components.audit_tools",
    "iast_scanner.core.model",
    "iast_scanner.core.modules",
    "iast_scanner.plugin",
    "iast_scanner.plugin.authorizer",
    "iast_scanner.plugin.deduplicate",
    "iast_scanner.plugin.scanner"
]

try:
    with open("iast_scanner/requirements.txt") as f:
        req_str = f.read()
    install_requires = req_str.split("\n")
except FileNotFoundError or Exception:
    install_requires = []

entry_points = {
    "console_scripts": [
        "iast-scanner=iast_scanner.main:run"
    ]
}

setuptools.setup(
    name='iast-scanner',
    version=open('iast_scanner/VERSION').read().strip(),
    description='An IAST scanner base on OpenRASP',
    long_description="An IAST scanner base on OpenRASP",
    author='OpenRASP',
    author_email='ext_yunfenxi@baidu.com',
    maintainer='G3G4X5X6',
    maintainer_email='g3g4x5x6@foxmail.com',
    url='https://github.com/openrasp-iast',
    packages=packages,
    install_requires=install_requires,
    package_dir={"iast_scanner": "iast_scanner"},
    include_package_data=True,
    entry_points=entry_points,
    platforms=["linux"],
    python_requires='>=3.6',
    license="Apache-2.0"
)
