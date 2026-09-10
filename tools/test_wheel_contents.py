import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from check_wheel_contents import check_wheel


class WheelContentsTests(unittest.TestCase):
    def test_runtime_data_and_exact_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.whl"
            provenance = dict(schema_version=1, source_revision="a" * 40, source_dirty=False,
                              version="4.0.0.dev0", core=dict(source_revision="b" * 40, source_dirty=False))
            with zipfile.ZipFile(path, "w") as wheel:
                wheel.writestr("pyopenms/_build_provenance.json", json.dumps(provenance))
                wheel.writestr("pyopenms/share/OpenMS/CHEMISTRY/unimod.xml", "<fixture/>")
            self.assertEqual(check_wheel(path, "a" * 40, "b" * 40), provenance)
            with self.assertRaisesRegex(ValueError, "Python source revision mismatch"):
                check_wheel(path, "c" * 40)
            with zipfile.ZipFile(path, "a") as wheel:
                wheel.writestr("pyopenms/share/OpenMS/test-data/core/test-only-marker.txt", "forbidden")
            with self.assertRaisesRegex(ValueError, "test/development data"):
                check_wheel(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
