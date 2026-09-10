"""Validate the loaded Core before importing scientific binding modules."""
import json
import platform


def validate_runtime_identity(expected, loaded):
    """Reject a replaced Core binary or incompatible wheel architecture.

    Compiler patch versions and the class-test build option are recorded but do
    not establish an ABI difference. Exact public dependency and feature choices
    belong to the artifact contract; PyArrow uses the separate C stream ABI.
    """
    if isinstance(loaded, str):
        loaded = json.loads(loaded)
    fields = (
        "schema_version", "source_revision", "source_dirty", "version",
        "build_type", "system_name", "system_processor", "cxx_compiler_id",
        "cxx_standard", "shared_libs", "stl_debug", "features", "dependencies",
    )
    for field in fields:
        if field not in expected or field not in loaded or expected[field] != loaded[field]:
            raise ImportError(
                f"OpenMS runtime identity mismatch for {field}: "
                f"wheel expects {expected.get(field)!r}, loaded {loaded.get(field)!r}"
            )
    aliases = {"aarch64": "arm64", "amd64": "x86_64"}
    machine = platform.machine().lower()
    core_machine = loaded["system_processor"].lower()
    if aliases.get(machine, machine) != aliases.get(core_machine, core_machine):
        raise ImportError(f"OpenMS runtime architecture mismatch: {core_machine} versus {machine}")
    return loaded
