"""Explicit paths to separately installed core and TOPP test fixtures."""

from __future__ import annotations

import os
from pathlib import Path


def _installed_fixture_dir(variable: str, package: str) -> str:
    value = os.environ.get(variable)
    if value and Path(value).is_dir():
        return str(Path(value).resolve())
    raise RuntimeError(
        f"Set {variable} to the installed {package} fixture directory. "
        "CMake/CTest sets it from the pinned SDK configuration; source-tree "
        "fallbacks are intentionally unsupported."
    )


def get_class_test_data_dir() -> str:
    """Read the OpenMS TestSupport component's OpenMS_TEST_DATA_DIR."""
    return _installed_fixture_dir("OPENMS_CLASS_TEST_DATA_PATH", "OpenMS TestSupport")


def get_topp_test_data_dir() -> str:
    """Read the fixture package's OpenMSTestData_TOPP_DIR."""
    return _installed_fixture_dir("OPENMS_TEST_DATA_PATH", "OpenMSTestData")
