#!/usr/bin/env python3
"""Fast source and fixture-contract tests; never import binary pyOpenMS modules."""

import ast
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "fixture_paths", ROOT / "tests/unittests/test_data_paths.py"
)
PATHS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATHS)


class InstalledFixtureTests(unittest.TestCase):
    def test_core_and_topp_have_independent_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            core = Path(temporary) / "core"
            topp = Path(temporary) / "topp"
            core.mkdir()
            topp.mkdir()
            with patch.dict(os.environ, {
                "OPENMS_CLASS_TEST_DATA_PATH": str(core),
                "OPENMS_TEST_DATA_PATH": str(topp),
            }, clear=True):
                self.assertEqual(PATHS.get_class_test_data_dir(), str(core.resolve()))
                self.assertEqual(PATHS.get_topp_test_data_dir(), str(topp.resolve()))

    def test_missing_fixture_packages_fail_explicitly(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "OPENMS_CLASS_TEST_DATA_PATH"):
                PATHS.get_class_test_data_dir()
            with self.assertRaisesRegex(RuntimeError, "OPENMS_TEST_DATA_PATH"):
                PATHS.get_topp_test_data_dir()

    def test_invalid_override_does_not_fall_back_to_other_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {
                "OPENMS_CLASS_TEST_DATA_PATH": str(Path(temporary) / "missing"),
                "OPENMS_TEST_DATA_PATH": temporary,
            }, clear=True):
                with self.assertRaisesRegex(RuntimeError, "OpenMS TestSupport"):
                    PATHS.get_class_test_data_dir()
                self.assertEqual(PATHS.get_topp_test_data_dir(), str(Path(temporary).resolve()))

    def test_fixture_path_must_be_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / "file"
            file.touch()
            with patch.dict(os.environ, {"OPENMS_TEST_DATA_PATH": str(file)}, clear=True):
                with self.assertRaises(RuntimeError):
                    PATHS.get_topp_test_data_dir()


class SourceCompletenessTests(unittest.TestCase):
    def test_python_sources_parse_without_importing_extensions(self):
        for directory in (ROOT / "pyopenms", ROOT / "tests"):
            for path in directory.rglob("*.py"):
                with self.subTest(path=path.relative_to(ROOT)):
                    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_all_domains_and_zero_copy_sources_exist(self):
        cmake = (ROOT / "CMakeLists.txt").read_text()
        domains = cmake.split("set(PYOPENMS_DOMAINS", 1)[1].split(")", 1)[0].split()
        for domain in domains:
            self.assertTrue((ROOT / "bindings" / f"bind_{domain}.cpp").is_file())
        self.assertEqual(len(domains), 13)
        for source in ("main_module.cpp", "arrow_zerocopy.cpp"):
            self.assertTrue((ROOT / "bindings" / source).is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
