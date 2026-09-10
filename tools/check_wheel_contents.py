#!/usr/bin/env python3
"""Inspect final wheel data and provenance without importing its native modules."""
import argparse
import json
from pathlib import PurePosixPath
import zipfile


def check_wheel(path, expected_source=None, expected_core=None, allow_dirty=False, no_share=False):
    with zipfile.ZipFile(path) as wheel:
        names = wheel.namelist()
        for name in names:
            parts = PurePosixPath(name).parts
            if parts[:3] == ("pyopenms", "share", "OpenMS"):
                if "test-data" in parts[3:] or "examples" in parts[3:]:
                    raise ValueError(f"Wheel contains test/development data: {name}")
                if no_share:
                    raise ValueError(f"NO_SHARE wheel contains runtime data: {name}")
        if not no_share and "pyopenms/share/OpenMS/CHEMISTRY/unimod.xml" not in names:
            raise ValueError("Wheel is missing chemistry runtime data")
        provenance = json.loads(wheel.read("pyopenms/_build_provenance.json"))
        if provenance.get("schema_version") != 1:
            raise ValueError("Unsupported wheel provenance schema")
        for identity, expected, label in ((provenance, expected_source, "Python"),
                                          (provenance["core"], expected_core, "Core")):
            revision = identity.get("source_revision", "")
            if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
                raise ValueError(f"Invalid {label} source revision")
            if expected and revision != expected:
                raise ValueError(f"{label} source revision mismatch")
            if type(identity.get("source_dirty")) is not bool:
                raise ValueError(f"Missing {label} dirty-source declaration")
            if identity["source_dirty"] and not allow_dirty:
                raise ValueError(f"{label} source is dirty; this is a development wheel")
        return provenance


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel")
    parser.add_argument("--expected-source")
    parser.add_argument("--expected-core")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--no-share", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check_wheel(args.wheel, args.expected_source, args.expected_core,
                                 args.allow_dirty, args.no_share), indent=2))
