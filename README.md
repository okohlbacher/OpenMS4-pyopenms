# Standalone pyOpenMS experiment

This repository contains the complete hand-maintained nanobind bindings, Python
package, addons, tests and local fixtures extracted from OpenMS at
`ca32296038839459d8c9b075b759e285913d6294`. The experimental Python release is
`4.0.0.dev0`. It builds against the separately installed OpenMS core SDK pinned
by version and full source revision in `dependencies.lock.json`.

## Installed dependencies

Provision the exact core SDK before configuring this package. Its CMake config
must export `OpenMS::Core`, `OpenMS::OpenSwathAlgo`, `OpenMS::Arrow`,
`Eigen3::Eigen`, `OpenMS_SOURCE_REVISION` and `OpenMS_SHARE_DIR`. Use the same
compiler, C++23 standard library ABI, platform, build configuration and shared
library choices as that SDK. No core source or core build directory is needed.
CMake disables its package registries and rejects mismatched SDK revisions.

Install Python build requirements from `pyproject.toml` into your chosen build
environment. Nanobind is fixed to 2.10.0; this package never downloads or patches
its C++ dependencies while configuring. Source provenance is in
`source-provenance.json`.

Once builds are authorized and the SDK exists:

```sh
python -m pip wheel . --no-build-isolation --no-deps \
  --config-settings=cmake.options.OpenMS_DIR=/sdk/lib/cmake/OpenMS
```

`OpenMS_DIR` names the directory containing the installed `OpenMSConfig.cmake`.
The example prefix is illustrative; use the actual pinned artifact's location.
The lock also belongs in source distributions, so archive builds perform the
same dependency check.

Wheels bundle the SDK's runtime data under `pyopenms/share/OpenMS`. Setting
`NO_SHARE=ON` opts out; then set `OPENMS_DATA_PATH` explicitly to the compatible
installed core data directory. Core's optional Thermo managed runtime remains
part of the SDK data. The Python package preserves its existing explicit bridge
lookup when those assemblies are bundled.

Shared-library repair uses auditwheel, delocate or delvewheel, as appropriate.
The release runner must provision the pinned SDK; the package does not install
system dependencies or select a mutable SDK container image. For Windows tests,
set `PYOPENMS_DLL_PATH` if transitive installed DLLs live outside the two core
library directories. `PYOPENMS_USE_PREBUILT` and `NO_DEPENDENCIES=OFF` are rejected:
arbitrary prebuilt output and the old in-tree dependency copier do not establish
this package's SDK identity.

## Tests and fixtures

The Python repository owns `tests/` and its local fixtures. The optional core
`TestSupport` component owns class-test fixtures. The separate `OpenMSTestData`
package owns TOPP fixtures. These packages are required only when configuring
`PYOPENMS_BUILD_TESTING=ON`; normal wheel builds need only core.

```sh
cmake -S . -B build \
  -DOpenMS_DIR=/sdk/lib/cmake/OpenMS \
  -DOpenMSTestData_DIR=/test-data/lib/cmake/OpenMSTestData \
  -DPYOPENMS_BUILD_TESTING=ON
cmake --build build
ctest --test-dir build --output-on-failure
```

CTest passes the installed paths as `OPENMS_CLASS_TEST_DATA_PATH` and
`OPENMS_TEST_DATA_PATH` and selects this package's build output via `PYTHONPATH`.
To test an installed wheel directly, set those two fixture variables and
`OPENMS_DATA_PATH`, then run `python -m pytest /path/to/this/repo/tests` from
outside the source package. Missing shared fixtures produce an explicit error;
there is no monorepo fallback. Install the `test` optional dependency group for
pytest, pandas, PyArrow and documentation checks. Optional real instrument data
continues to use the existing explicit test variables.

Fast checks that require neither core binaries nor a compiler:

```sh
python tools/check_standalone.py
python tools/check_cmake_contract.py  # POSIX; CMake required, compiler never invoked
```

This checks fixture resolution, Python syntax and binding source completeness.
The configure checks use fake installed targets to
verify SDK discovery and test registration; such checks cannot establish binary
correctness.

## Provenance and remaining acceptance gates

After compilation, `pyopenms.__version__` reports the Python package version;
`pyopenms.__openms_core_version__` and `pyopenms.__openms_core_revision__` report
its build-time core SDK identity. These metadata values do not detect a replaced
runtime library by themselves. Artifact digest verification and the full ABI
manifest remain the release composition layer's responsibility.

No native compilation or binary tests were performed during extraction. Before
publishing a wheel, build an sdist in a clean runner with core source/build trees
unavailable, run the complete Python test suite against installed fixtures, repair
and relocate the wheel, and repeat import, resource, numerical and Arrow/PyArrow
round-trip tests. Validate every supported platform and the optional raw-file
features. The existing PyArrow filesystem workaround depends on private PyArrow
APIs; sharing the SDK Arrow target fixes C++ linkage selection but does not prove
compatibility with every PyArrow wheel. The removed MSVC nanobind header rewrite
also requires compile-time performance validation with the unmodified dependency.

Historical wrapping documentation, `pxds/` and `pyTOPP/` examples are preserved
for provenance. The active build uses only `bindings/*.cpp`; the legacy Cython
files are not a second supported binding implementation.
