"""Native wheel identity and catchable first-data-lookup regression checks."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pyopenms as oms


def test_loaded_core_matches_embedded_wheel_identity():
    provenance = json.loads((Path(oms.__file__).parent / "_build_provenance.json").read_text())
    loaded = json.loads(oms.VersionInfo.getBuildInfo())
    assert loaded == oms.__openms_runtime_build_info__
    assert loaded["source_revision"] == provenance["core"]["source_revision"]
    assert oms.VersionInfo.getSourceRevision() == oms.__openms_core_revision__
    assert oms.VersionInfo.isSourceDirty() == provenance["core"]["source_dirty"]
    assert len(oms.__source_revision__) == 40
    assert oms.__source_dirty__ == provenance["source_dirty"]


def test_bad_data_override_can_be_caught_and_import_retried(tmp_path):
    env = dict(os.environ, OPENMS_DATA_PATH=str(tmp_path / "missing"),
               PYOPENMS_VALID_DATA_PATH=oms.File.getOpenMSDataPath())
    code = '''
import os
try:
    import pyopenms
except RuntimeError as error:
    assert "OPENMS_DATA_PATH" in str(error), str(error)
    assert "Cannot find shared data" in str(error), str(error)
else:
    raise AssertionError("invalid override was accepted")
os.environ["OPENMS_DATA_PATH"] = os.environ["PYOPENMS_VALID_DATA_PATH"]
import pyopenms
assert pyopenms.File.getOpenMSDataPath() == os.environ["PYOPENMS_VALID_DATA_PATH"]
assert pyopenms.AASequence.fromString("PEPTIDE").getMonoWeight() > 0
print("caught data failure and retried successfully")
'''
    result = subprocess.run([sys.executable, "-c", code], env=env, text=True,
                            capture_output=True, cwd=tmp_path, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "caught data failure and retried successfully" in result.stdout
