import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from run import archive_install, check_install, core_prefix, wheel_test_environment
from run import test_environment as fixture_environment


class PackagingTest(unittest.TestCase):
    def test_archive_and_core_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core = root / "extracted" / "core"
            core.mkdir(parents=True)
            (core / "source-revision.txt").write_text("a" * 40 + "\n", encoding="utf-8")
            self.assertEqual(core_prefix(root / "extracted"), core)
            payload = root / "payload"
            payload.mkdir()
            (payload / "value").write_text("ok", encoding="utf-8")
            archive = archive_install(payload, root / "dist", "package")
            self.assertTrue(archive.is_file())
            self.assertEqual(len(archive.with_suffix(".gz.sha256").read_text().split()[0]), 64)

    def test_check_install_requires_module_and_stubs(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            with self.assertRaises(ValueError):
                check_install(prefix, sys.executable)
            module = prefix / "pyopenms"
            module.mkdir()
            (module / "__init__.py").write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):  # stubs are part of the contract
                check_install(prefix, sys.executable)
            (module / "pyopenms.pyi").write_text("", encoding="utf-8")
            check_install(prefix, sys.executable)

    def test_wheel_uses_fixtures_without_ctest_build_paths(self):
        tests = {"tests": [{"name": "pyopenms_unittests", "command": [
            "cmake", "-E", "env", "PYTHONPATH=C:/build/pyopenms",
            "PYOPENMS_DLL_PATH=C:/sdk/bin;C:/conda/Library/bin",
            "OPENMS_DATA_PATH=C:/sdk/share/OpenMS",
            "OPENMS_CLASS_TEST_DATA_PATH=C:/sdk/test-data",
            "OPENMS_TEST_DATA_PATH=C:/fixtures", "OPENTIMS_DDA_TEST_DATA=C:/instrument",
            "python", "-m", "pytest", "--ignore=tests/docstrings.py"]}]}
        with patch("run.subprocess.check_output", return_value=json.dumps(tests)):
            fixtures = fixture_environment(Path("build"), "Release")
        self.assertEqual(fixtures, {
            "OPENMS_CLASS_TEST_DATA_PATH": "C:/sdk/test-data",
            "OPENMS_TEST_DATA_PATH": "C:/fixtures",
            "OPENTIMS_DDA_TEST_DATA": "C:/instrument"})

    def test_wheel_environment_rejects_inherited_python_and_native_paths(self):
        overrides = {key: "unrepaired-sdk" for key in (
            "PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "PYOPENMS_DLL_PATH",
            "OPENMS_DATA_PATH", "OPENMS_THERMO_MANAGED_DIR", "LD_LIBRARY_PATH",
            "LD_PRELOAD", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH",
            "DYLD_FRAMEWORK_PATH", "DYLD_FALLBACK_FRAMEWORK_PATH", "DYLD_INSERT_LIBRARIES")}
        inherited = dict(os.environ, **overrides, PATH="unrepaired-sdk/bin")
        clean = wheel_test_environment(inherited, Path(sys.executable).parent)
        self.assertFalse(set(overrides) & set(clean))
        self.assertNotIn("unrepaired-sdk", clean["PATH"])
        self.assertEqual(clean["PYTHONNOUSERSITE"], "1")
        # Windows environment keys are case-insensitive, and DLL lookup must not
        # inherit conda/build entries through either Path or PYOPENMS_DLL_PATH.
        with patch("run.sys.platform", "win32"):
            windows = wheel_test_environment({"Path": "C:/conda/Library/bin",
                                              "PythonPath": "C:/build",
                                              "SystemRoot": "C:/Windows"}, Path("venv/Scripts"))
        self.assertNotIn("Path", windows)
        self.assertNotIn("PythonPath", windows)
        self.assertEqual(windows["PATH"], os.pathsep.join(
            [str(Path("venv/Scripts")), str(Path("C:/Windows") / "System32"), "C:/Windows"]))
        with tempfile.TemporaryDirectory() as directory:
            shadow = Path(directory) / "build"
            shadow.mkdir()
            (shadow / "unrepaired_pyopenms.py").write_text("raise RuntimeError('shadowed')\n")
            inherited["PYTHONPATH"] = str(shadow)
            clean = wheel_test_environment(inherited, Path(sys.executable).parent)
            subprocess.run([sys.executable, "-c",
                            "import importlib.util; "
                            "assert importlib.util.find_spec('unrepaired_pyopenms') is None"],
                           cwd=directory, env=clean, check=True)


if __name__ == "__main__":
    unittest.main()
