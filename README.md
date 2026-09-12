# Optional scientific tool backends

The default full API additionally consumes the exact installed OpenMSProSE and
OpenMSFLASH backend SDKs in `dependencies.lock.json`. These libraries require Core,
not their executables or CLI. Existing ProSEAlgorithm, FLASHDeconvAlgorithm and
SpectralDeconvolution Python methods remain available with their original names.
Wheel repair must bundle the selected backend libraries along with Core.

For an explicitly reduced Core-only API, configure
`-DPYOPENMS_WITH_PROSE=OFF -DPYOPENMS_WITH_FLASH=OFF`; the corresponding classes are
then intentionally absent. Build provenance records selected backend revisions.
Do not replace Core or a backend beneath an already-built wheel: rebuild against
matching source pins and the same native build configuration.

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
The SDK must provide `OpenMS_BUILD_INFO_FILE`. Configuration also checks its
platform, architecture, configuration, C++ standard, shared linkage and required
OpenSWATH feature. A multi-configuration build exposes only the SDK's configuration.

Install Python build requirements from `pyproject.toml` into your chosen build
environment. Nanobind is fixed to 2.10.0; this package never downloads or patches
its C++ dependencies while configuring. Source provenance is in
`source-provenance.json`.
The pinned nanobind 2.10.0 has a dependency-discovery regression; the supported
`NB_USE_SUBMODULE_DEPS=ON` setting selects the headers already shipped in its wheel.
No third-party source is patched.

Once builds are authorized and the SDK exists:

```sh
python -m pip wheel . --no-build-isolation --no-deps \
  --config-settings=override=cmake.options.OpenMS_DIR=/sdk/lib/cmake/OpenMS
```

`OpenMS_DIR` names the directory containing the installed `OpenMSConfig.cmake`.
The example prefix is illustrative; use the actual pinned artifact's location.
The lock also belongs in source distributions, so archive builds perform the
same dependency check.
Archive builds must explicitly supply `OPENMS4_SOURCE_REVISION` and
`OPENMS4_SOURCE_DIRTY`. Git builds record the actual HEAD, tracked changes and
non-ignored untracked inputs;
`OPENMS4_REQUIRE_CLEAN_SOURCE=ON` rejects dirty sources for publishable builds.
The wheel backend defaults to Release, so use a matching Release SDK for that
command. For Debug development, configure CMake directly with
`-DCMAKE_BUILD_TYPE=Debug` against the Debug SDK, or pass the wheel backend
`--config-settings=override=cmake.build_type=Debug`.

Wheels bundle the SDK's runtime data under `pyopenms/share/OpenMS`. Setting
`NO_SHARE=ON` opts out; then set `OPENMS_DATA_PATH` explicitly to the compatible
installed core data directory. Core's optional Thermo managed runtime remains
part of the SDK data. The Python package preserves its existing explicit bridge
lookup when those assemblies are bundled.
TestSupport's `test-data` and SDK examples are excluded. Reconfiguration removes
old staged share data, and installation clears the package-owned share directory
before copying; switching to `NO_SHARE=ON` also removes a prior bundled payload.

Shared-library repair uses auditwheel, delocate or delvewheel, as appropriate.
CI does exactly this after its native build: `tools/ci/run.py` builds the wheel
through the PEP 517 backend against the same installed chain, repairs it, installs
it into a fresh virtual environment with no build prefix on any library path and
runs the whole test suite from there. The repaired wheel is uploaded next to the
installed-tree archive and published with each release. It is built for the CI
environment's Python (3.12); other interpreters need their own build for now.
Before that test, CI checks the wheel's exact source/Core revisions and bundled
data, removes inherited Python and native library overrides (including Windows
DLL paths), and verifies that Python imports the copy installed in the fresh
environment. Only explicit test-fixture paths are carried over from CTest.
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
  -DCMAKE_BUILD_TYPE=Debug \
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
python tools/test_runtime_identity.py
python tools/test_wheel_contents.py
```

This checks fixture resolution, Python syntax and binding source completeness.
The configure checks use fake installed targets to
verify SDK discovery and test registration; such checks cannot establish binary
correctness.

The small native Arrow probe uses the same `bindings/arrow_table.h` as the real
bindings, with no Core algorithms compiled. It requires installed Arrow,
nanobind and PyArrow:

```sh
cmake -S tools/native_arrow -B build-arrow -DCMAKE_BUILD_TYPE=Debug \
  -DPython_EXECUTABLE=/path/to/python
cmake --build build-arrow --parallel 2
ctest --test-dir build-arrow --output-on-failure
```

It tests empty-schema preservation, multiple batches forced at the C stream
boundary, producer garbage collection, malformed capsules, and stream errors.
All import helpers accept an Arrow C stream provider (including PyArrow tables
and readers), consume every batch, and retain Arrow release ownership. The C
interface transfers buffers without copying; scientific object conversion and
combining output chunks can still copy. No end-to-end zero-copy guarantee is made.

The same production helper can be checked with AddressSanitizer and
UndefinedBehaviorSanitizer, without another test implementation. On macOS with
AppleClang, preload its sanitizer runtime into Python directly:

```sh
cmake -S tools/native_arrow -B build-arrow-sanitized -DCMAKE_BUILD_TYPE=Debug \
  -DPython_EXECUTABLE=/path/to/python \
  '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer'
cmake --build build-arrow-sanitized --parallel 1
DYLD_INSERT_LIBRARIES="$(xcrun clang --print-resource-dir)/lib/darwin/libclang_rt.asan_osx_dynamic.dylib" \
  ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 \
  UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
  PYTHONPATH="$PWD/build-arrow-sanitized" \
  /path/to/python -m pytest tools/native_arrow/test_arrow_table.py
```

Use the same installed dependency search paths as the ordinary probe. Launching
through intermediate programs can lose the macOS preload variable; the direct
Python invocation above is required for this profile. All four cases passed
under both sanitizers with AppleClang 21 on macOS arm64. This instruments the
helper and nanobind; installed Arrow, PyArrow and Python remain uninstrumented.
Leak detection is disabled for this Darwin profile, so it is not a leak check.

## Provenance and remaining acceptance gates

After compilation, `pyopenms.__version__` reports the Python package version;
`pyopenms.__openms_core_version__` and `pyopenms.__openms_core_revision__` report
its build-time core SDK identity. `__source_revision__` and `__source_dirty__`
identify this Python package's own source. `_build_provenance.json` carries the
same data plus the Core build identity without requiring execution of wheel code.

Before scientific modules load, the small native entry module reports the loaded
Core's `VersionInfo.getBuildInfo()`. Import rejects source, architecture,
configuration, standard-library/CRT ABI, feature or public-dependency differences from the embedded Core
identity. Compiler patch versions and class-test configuration are recorded but
do not by themselves imply an ABI difference. `__openms_runtime_build_info__`
exposes the accepted loaded identity. Artifact hashes and native wheel tests
remain necessary; matching metadata alone is not a universal ABI proof.

An invalid `OPENMS_DATA_PATH` raises a catchable exception before domain imports.
Correct the override and retry the import; successful Core data lookup remains
cached for the process. Native tests exercise this in a fresh Python process.

Inspect every final repaired wheel, including one built from reused staging:

```sh
python tools/check_wheel_contents.py dist/pyopenms-<tags>.whl \
  --expected-source <python-commit> --expected-core <core-commit>
```

The check rejects test/example data, absent chemistry data, wrong revisions and
dirty source declarations. Use `--no-share` only for intentionally unbundled
data, or `--allow-dirty` for explicitly marked development wheels.

The original extraction performed no native Python validation. The later isolated
Arrow probe passed four cases with AppleClang 21, Arrow C++ 25 and PyArrow 23.0.1
on macOS arm64; the host's existing Abseil dependency required the documented
loader fallback from the parent Core report. That probe is not a repaired-wheel
or complete scientific-binding test. Before
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
