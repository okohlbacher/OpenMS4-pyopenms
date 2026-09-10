# Extraction validation — 2026-09-10

- `python3 tools/check_standalone.py`: **6 tests passed**. Verified independent
  installed fixture paths, missing/invalid fixture failure, 13 domain binding
  sources plus main and Arrow modules, and Python syntax across package/tests.
- `tools/check_cmake_contract.py`: **normal and test-enabled configuration passed**
  using fake installed SDK, nanobind and Python metadata. A wrong 40-character
  core revision was rejected before module creation. Test-enabled configuration
  registered all four existing CTest groups (`ctest -N`, no tests executed).
  The fake toolchain uses `/usr/bin/true`, marks compiler identification complete
  and never invokes a compiler or build command.
- Static sdist inclusion scan found **no uncovered files** under `bindings/`,
  `pyopenms/`, `tests/`, `cmake/` and `tools/`. The integration owner finalizes
  `dependencies.lock.json` before committing this subrepository.
- No binding implementation source was rewritten. No OpenMS/native compilation,
  dependency installation, runtime extension import, numerical test or wheel
  repair was performed.

Existing syntax warning: `tests/unittests/test_chaining_semantics.py` has an
invalid escape in its documentation string. Parsing succeeds; the warning is
unrelated to extraction.

Pending acceptance: real pinned SDK installation, sdist-to-wheel build with core
source/build trees absent, complete runtime tests against installed fixtures,
wheel relocation/repair on every target platform, optional raw formats, and
Arrow/PyArrow interoperability. Configuration checks do not establish these.
