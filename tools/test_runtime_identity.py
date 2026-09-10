"""Exercise the import guard without importing any native scientific modules."""
import copy
import importlib.util
import json
from pathlib import Path
import platform
import unittest

SPEC = importlib.util.spec_from_file_location(
    "runtime_identity", Path(__file__).resolve().parents[1] / "pyopenms/_runtime_identity.py")
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class RuntimeIdentityTests(unittest.TestCase):
    def setUp(self):
        self.identity = dict(
            schema_version=1, source_revision="a" * 40, source_dirty=False,
            version="4.0.0", build_type="Debug", system_name=platform.system(),
            system_processor=platform.machine(), cxx_compiler_id="Clang",
            cxx_compiler_version="17.0.0", cxx_standard=23, shared_libs=True,
            class_testing_enabled=True, stl_debug=False, features={"openswath": True},
            dependencies={"arrow": {"version": "25.0.0", "linkage": "shared"}},
        )

    def test_matching_loaded_identity_and_incidental_metadata(self):
        loaded = copy.deepcopy(self.identity)
        loaded.update(cxx_compiler_version="17.0.1", class_testing_enabled=False)
        self.assertEqual(GUARD.validate_runtime_identity(self.identity, json.dumps(loaded)), loaded)

    def test_rejects_wrong_binary_source_and_required_abi_fields(self):
        for key, value in {
            "source_revision": "b" * 40, "source_dirty": True,
            "build_type": "Release", "system_processor": "wrong-architecture",
            "features": {"openswath": False}, "dependencies": {},
            "shared_libs": False,
        }.items():
            with self.subTest(field=key):
                loaded = dict(self.identity, **{key: value})
                with self.assertRaisesRegex(ImportError, key):
                    GUARD.validate_runtime_identity(self.identity, loaded)

    def test_missing_runtime_fields_fail_explicitly(self):
        with self.assertRaisesRegex(ImportError, "schema_version"):
            GUARD.validate_runtime_identity(self.identity, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
