"""Shared fixtures for testing an installed or explicitly selected pyOpenMS build.

CTest sets PYTHONPATH to this package's build output. Wheel tests import the
installed wheel. Test collection never searches for a monorepo build directory.
"""

from .unittests.test_data_paths import get_topp_test_data_dir

try:
    import pytest
except ImportError:
    pytest = None


def _get_test_data_dir():
    """Resolve TOPP fixtures explicitly supplied by the installed data package."""
    return get_topp_test_data_dir()


if pytest is not None:
    @pytest.fixture(scope="session")
    def openms_test_data_dir():
        return _get_test_data_dir()
