# Copyright (c) 2002-present, OpenMS Inc. -- EKU Tuebingen, ETH Zurich, and FU Berlin
# SPDX-License-Identifier: BSD-3-Clause
# Standalone pyOpenMS: hand-maintained bindings consume an installed, pinned SDK.
cmake_minimum_required(VERSION 3.24 FATAL_ERROR)
project(pyOpenMS VERSION 4.0.0 LANGUAGES CXX)
set(PYOPENMS_PACKAGE_VERSION "4.0.0.dev0")
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(NO_SHARE "Do not bundle installed core runtime data into the wheel" OFF)
option(NO_DEPENDENCIES "Leave shared-library bundling to wheel repair tools" ON)
option(PYOPENMS_BUILD_TESTING "Register tests using installed core and TOPP fixture packages" OFF)
option(PYOPENMS_GENERATE_STUBS "Generate .pyi stub files" ON)
option(PYOPENMS_PREPARE_WHEEL_REPAIR "Set RPATH for auditwheel/delocate/delvewheel" OFF)
set(PYOPENMS_DLL_PATH "" CACHE STRING "Additional installed runtime DLL directories for tests")

if(PYOPENMS_USE_PREBUILT)
  message(FATAL_ERROR "Unverified prebuilt reuse is unsupported; build this package against its pinned installed SDK")
endif()
if(NOT NO_DEPENDENCIES)
  message(FATAL_ERROR "Use wheel repair tools to bundle the pinned installed libraries (NO_DEPENDENCIES=ON)")
endif()

# Never resolve a previously configured source/build tree through CMake's registry.
set(CMAKE_FIND_USE_PACKAGE_REGISTRY OFF)
set(CMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY OFF)
include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/OpenMS4Dependencies.cmake")
if(PYOPENMS_BUILD_TESTING)
  openms4_find_core(COMPONENTS Core TestSupport)
  openms4_find_package(OpenMSTestData)
else()
  openms4_find_core(COMPONENTS Core)
endif()
foreach(_target OpenMS::Core OpenMS::OpenSwathAlgo OpenMS::Arrow Eigen3::Eigen)
  if(NOT TARGET ${_target})
    message(FATAL_ERROR "The installed OpenMS SDK does not provide required target ${_target}")
  endif()
endforeach()
foreach(_target OpenMS::Core OpenMS::OpenSwathAlgo)
  get_target_property(_imported ${_target} IMPORTED)
  if(NOT _imported)
    message(FATAL_ERROR "${_target} must come from an installed SDK, not an in-tree core build")
  endif()
endforeach()
set(OPENMS_TARGET OpenMS::Core)
set(OPENSWATHALGO_TARGET OpenMS::OpenSwathAlgo)
set(CF_OPENMS_PACKAGE_VERSION "${OpenMS_VERSION}")
include(cmake/PyOpenMSBuildIdentity.cmake)

# The SDK owns runtime data. Wheel builds never search a sibling source tree.
set(OPENMS_SHARE_DIR "${OpenMS_SHARE_DIR}")
if(NOT NO_SHARE AND NOT EXISTS "${OPENMS_SHARE_DIR}/CHEMISTRY/unimod.xml")
  message(FATAL_ERROR "The installed core SDK must export OpenMS_SHARE_DIR with complete runtime data")
endif()

find_package(Python 3.10 REQUIRED COMPONENTS Interpreter Development.Module NumPy)
# Python build requirements supply nanobind; configuring never fetches or patches it.
execute_process(COMMAND "${Python_EXECUTABLE}" -m nanobind --cmake_dir
  OUTPUT_STRIP_TRAILING_WHITESPACE OUTPUT_VARIABLE nanobind_ROOT
  RESULT_VARIABLE _nanobind_result)
if(NOT _nanobind_result EQUAL 0)
  message(FATAL_ERROR "Install this package's Python build requirements, including nanobind")
endif()
find_package(nanobind 2.10.0 EXACT CONFIG REQUIRED)
# 2.10.0 requires this explicit choice to use its wheel's shipped robin_map.
set(NB_USE_SUBMODULE_DEPS ON CACHE BOOL "Use dependencies shipped in the pinned nanobind wheel")

if(UNIX AND NOT APPLE AND NOT CYGWIN)
  set(LINUX TRUE)
endif()
set(PYOPENMS_BUILD_DIR "${CMAKE_CURRENT_BINARY_DIR}/pyOpenMS")
# Imports during stub generation and tests need the same installed DLL search path.
set(_pyopenms_python_cmd "${CMAKE_COMMAND}" -E env "PYTHONPATH=${PYOPENMS_BUILD_DIR}")
if(WIN32)
  set(_pyopenms_dll_dirs "$<TARGET_FILE_DIR:OpenMS::Core>$<SEMICOLON>$<TARGET_FILE_DIR:OpenMS::OpenSwathAlgo>")
  if(PYOPENMS_DLL_PATH)
    string(REPLACE ";" "$<SEMICOLON>" _extra_dll_dirs "${PYOPENMS_DLL_PATH}")
    string(APPEND _pyopenms_dll_dirs "$<SEMICOLON>${_extra_dll_dirs}")
  endif()
  list(APPEND _pyopenms_python_cmd "PYOPENMS_DLL_PATH=${_pyopenms_dll_dirs}")
endif()
set(PYOPENMS_DOMAINS
  kernel metadata chemistry analysis featurefinder format processing datastructures ml misc
  spectrum chromatogram experiment)

# --------------------------------------------------------------------------
# RPATH settings
# --------------------------------------------------------------------------
if(NOT PYOPENMS_PREPARE_WHEEL_REPAIR)
  set(PY_RPATH ${CMAKE_INSTALL_RPATH})
  if(APPLE)
    list(APPEND PY_RPATH "@loader_path/")
  elseif(LINUX)
    list(APPEND PY_RPATH "$ORIGIN/")
  endif()
  message(STATUS "pyOpenMS: PY_RPATH = '${PY_RPATH}'")
else()
  set(PY_RPATH "")
  message(STATUS "Preparing modules for wheel repair: INSTALL_RPATH_USE_LINK_PATH enabled")
endif()

# --------------------------------------------------------------------------
# Setup build directories
# --------------------------------------------------------------------------
file(MAKE_DIRECTORY ${PYOPENMS_BUILD_DIR})
file(MAKE_DIRECTORY ${PYOPENMS_BUILD_DIR}/pyopenms)
file(MAKE_DIRECTORY ${PYOPENMS_BUILD_DIR}/pyopenms/addons)

# --------------------------------------------------------------------------
# Hand-maintained nanobind binding sources
# --------------------------------------------------------------------------
set(PYOPENMS_BINDINGS_DIR "${CMAKE_CURRENT_SOURCE_DIR}/bindings")

set(PYOPENMS_BINDING_SOURCES "${PYOPENMS_BINDINGS_DIR}/main_module.cpp")
foreach(domain ${PYOPENMS_DOMAINS})
  list(APPEND PYOPENMS_BINDING_SOURCES "${PYOPENMS_BINDINGS_DIR}/bind_${domain}.cpp")
endforeach()

# Verify binding sources exist
foreach(_src ${PYOPENMS_BINDING_SOURCES})
  if(NOT EXISTS "${_src}")
    message(FATAL_ERROR "Binding source not found: ${_src}")
  endif()
endforeach()

# --------------------------------------------------------------------------
# Build split nanobind modules for parallel compilation
# --------------------------------------------------------------------------

# Helper function to set common module properties
function(_pyopenms_module_props target_name)
  target_include_directories(${target_name} PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/bindings/type_casters"
  )
  target_link_libraries(${target_name} PRIVATE
    ${OPENMS_TARGET}
    ${OPENSWATHALGO_TARGET}
    Eigen3::Eigen
  )
  # The trailing "$<0:>" is an (empty) generator expression: it makes CMake use
  # this path verbatim instead of appending a per-configuration subdirectory on
  # multi-config generators (Visual Studio, Xcode). Without it the modules land
  # in pyopenms/Release/, where pyopenms/__init__.py (pkgutil.iter_modules, which
  # does not recurse) cannot find them, and `import pyopenms` fails with
  # "Failed to import any pyOpenMS bindings".
  set_target_properties(${target_name} PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${PYOPENMS_BUILD_DIR}/pyopenms/$<0:>"
    RUNTIME_OUTPUT_DIRECTORY "${PYOPENMS_BUILD_DIR}/pyopenms/$<0:>"
  )
  if(NOT PYOPENMS_PREPARE_WHEEL_REPAIR)
    set_target_properties(${target_name} PROPERTIES
      INSTALL_RPATH "${PY_RPATH}"
    )
    if(APPLE)
      set_target_properties(${target_name} PROPERTIES
        BUILD_WITH_INSTALL_NAME_DIR 1
      )
    endif()
  else()
    set_target_properties(${target_name} PROPERTIES
      INSTALL_RPATH_USE_LINK_PATH TRUE
      INSTALL_NAME_DIR ""
    )
  endif()
  install(TARGETS ${target_name}
    LIBRARY DESTINATION pyopenms COMPONENT python_modules
    RUNTIME DESTINATION pyopenms COMPONENT python_modules
  )
endfunction()

# Build each domain submodule
foreach(domain ${PYOPENMS_DOMAINS})
  set(MODULE_NAME "_pyopenms_${domain}")

  nanobind_add_module(${MODULE_NAME}
    NB_DOMAIN pyopenms  # Share types across modules
    NOMINSIZE            # Use CMake's default -O3 instead of nanobind's -Os
    ${PYOPENMS_BINDINGS_DIR}/bind_${domain}.cpp
  )
  _pyopenms_module_props(${MODULE_NAME})
endforeach()

# Main entry module
nanobind_add_module(_pyopenms
  NB_DOMAIN pyopenms
  NOMINSIZE
  ${PYOPENMS_BINDINGS_DIR}/main_module.cpp
)
_pyopenms_module_props(_pyopenms)

# --------------------------------------------------------------------------
# Arrow zero-copy export
# --------------------------------------------------------------------------
# Use the Arrow ABI and linkage selected by the pinned core SDK.
message(STATUS "pyOpenMS: Building _arrow_zerocopy module")
nanobind_add_module(_arrow_zerocopy
  NB_DOMAIN pyopenms
  NOMINSIZE
  ${CMAKE_CURRENT_SOURCE_DIR}/bindings/arrow_zerocopy.cpp
)
_pyopenms_module_props(_arrow_zerocopy)
# arrow_zerocopy.cpp uses Arrow C++ API (ExportSchema, ImportRecordBatch, etc.)
# for zero-copy Table conversion between C++ and PyArrow.
target_link_libraries(_arrow_zerocopy PRIVATE OpenMS::Arrow)

# --------------------------------------------------------------------------
# Aggregate compile target
# --------------------------------------------------------------------------
add_custom_target(pyopenms_compile ALL)
add_dependencies(pyopenms_compile _pyopenms)
foreach(domain ${PYOPENMS_DOMAINS})
  add_dependencies(pyopenms_compile "_pyopenms_${domain}")
endforeach()
add_dependencies(pyopenms_compile _arrow_zerocopy)

# --------------------------------------------------------------------------
# Copy Python package files to build directory
# --------------------------------------------------------------------------

# Helper function to copy assets
function(_copy_assets _asset_dir _regex _target_dir)
  file(GLOB _assets "${_asset_dir}/${_regex}")
  foreach(_asset_file ${_assets})
    file(RELATIVE_PATH _relative_path ${_asset_dir} ${_asset_file})
    if(NOT IS_DIRECTORY ${_asset_file})
      configure_file(${_asset_file} ${_target_dir}/${_relative_path} COPYONLY)
    endif()
  endforeach()
endfunction()

# Core Python files
_copy_assets("${PROJECT_SOURCE_DIR}/pyopenms/" "*.py" "${PYOPENMS_BUILD_DIR}/pyopenms/")
_copy_assets("${PROJECT_SOURCE_DIR}/pyopenms/" "py.typed" "${PYOPENMS_BUILD_DIR}/pyopenms/")

# Addon files
_copy_assets("${PROJECT_SOURCE_DIR}/pyopenms/addons/" "*.py" "${PYOPENMS_BUILD_DIR}/pyopenms/addons/")
configure_file("${PROJECT_SOURCE_DIR}/cmake/_build_provenance.py.in"
  "${PYOPENMS_BUILD_DIR}/pyopenms/_build_provenance.py" @ONLY)
file(WRITE "${PYOPENMS_BUILD_DIR}/pyopenms/_build_provenance.json" "${_pyopenms_provenance}\n")

# Reconfiguration must remove data left by older, unfiltered staging or NO_SHARE.
file(REMOVE_RECURSE "${PYOPENMS_BUILD_DIR}/pyopenms/share")
if(NOT NO_SHARE AND DEFINED OPENMS_SHARE_DIR AND EXISTS "${OPENMS_SHARE_DIR}")
  file(MAKE_DIRECTORY ${PYOPENMS_BUILD_DIR}/pyopenms/share/OpenMS)
  file(COPY "${OPENMS_SHARE_DIR}/" DESTINATION "${PYOPENMS_BUILD_DIR}/pyopenms/share/OpenMS"
      PATTERN "examples" EXCLUDE PATTERN "test-data" EXCLUDE)
endif()

# --------------------------------------------------------------------------
# Stub generation
# --------------------------------------------------------------------------
if(PYOPENMS_GENERATE_STUBS)
  add_custom_target(pyopenms_stubs
    COMMAND ${_pyopenms_python_cmd} "${Python_EXECUTABLE}" -m nanobind.stubgen
            -m pyopenms
            -r                          # recurse into submodules
            -P                          # include private members
            -O ${PYOPENMS_BUILD_DIR}/pyopenms
            -M ${PYOPENMS_BUILD_DIR}/pyopenms/py.typed
            -p ${CMAKE_CURRENT_SOURCE_DIR}/stubs.patch
    COMMAND ${Python_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/fix_stubs.py
            ${PYOPENMS_BUILD_DIR}/pyopenms
    WORKING_DIRECTORY ${PYOPENMS_BUILD_DIR}
    DEPENDS pyopenms_compile
    COMMENT "Generating .pyi stub files for pyopenms"
  )
endif()


# Install the assembled Python package; platform libraries are handled by wheel repair.
# A reused wheel install prefix must not retain fixtures or a previous NO_SHARE payload.
install(CODE [[file(REMOVE_RECURSE "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/pyopenms/share")]]
  COMPONENT python_modules)
install(DIRECTORY "${PYOPENMS_BUILD_DIR}/pyopenms/"
  DESTINATION pyopenms COMPONENT python_modules FILES_MATCHING
  PATTERN "*.py" PATTERN "*.pyi" PATTERN "py.typed" PATTERN "__pycache__" EXCLUDE)
install(FILES "${PYOPENMS_BUILD_DIR}/pyopenms/_build_provenance.json"
  DESTINATION pyopenms COMPONENT python_modules)
if(NOT NO_SHARE)
  install(DIRECTORY "${PYOPENMS_BUILD_DIR}/pyopenms/share"
    DESTINATION pyopenms COMPONENT python_modules
    PATTERN "test-data" EXCLUDE PATTERN "examples" EXCLUDE)
endif()
add_custom_target(pyopenms ALL)
add_dependencies(pyopenms pyopenms_compile)
if(PYOPENMS_GENERATE_STUBS)
  add_dependencies(pyopenms pyopenms_stubs)
endif()

# Register tests independently of the core build and use installed fixtures.
if(PYOPENMS_BUILD_TESTING)
  foreach(_fixture_dir OpenMS_TEST_DATA_DIR OpenMSTestData_TOPP_DIR)
    if(NOT IS_DIRECTORY "${${_fixture_dir}}")
      message(FATAL_ERROR "Installed fixture directory ${_fixture_dir} is missing")
    endif()
  endforeach()
  enable_testing()
  file(COPY "${PROJECT_SOURCE_DIR}/tests" DESTINATION "${PYOPENMS_BUILD_DIR}")
  set(_pyopenms_test_cmd_prefix ${_pyopenms_python_cmd}
    "OPENMS_DATA_PATH=${OPENMS_SHARE_DIR}"
    "OPENMS_CLASS_TEST_DATA_PATH=${OpenMS_TEST_DATA_DIR}"
    "OPENMS_TEST_DATA_PATH=${OpenMSTestData_TOPP_DIR}")
  foreach(_data OPENTIMS_DDA_TEST_DATA OPENTIMS_DIA_TEST_DATA)
    if(${_data})
      list(APPEND _pyopenms_test_cmd_prefix "${_data}=${${_data}}")
    endif()
  endforeach()
  add_test(NAME pyopenms_unittests
    COMMAND ${_pyopenms_test_cmd_prefix} "${Python_EXECUTABLE}" -m pytest
      --ignore=tests/unittests/test_docstrings.py
      --ignore=tests/unittests/test_docstring_format.py tests/unittests
    WORKING_DIRECTORY "${PYOPENMS_BUILD_DIR}")
  add_test(NAME pyopenms_docstring_tests
    COMMAND ${_pyopenms_test_cmd_prefix} "${Python_EXECUTABLE}" -m pytest
      tests/unittests/test_docstrings.py tests/unittests/test_docstring_format.py
    WORKING_DIRECTORY "${PYOPENMS_BUILD_DIR}")
  add_test(NAME pyopenms_integration_tests
    COMMAND ${_pyopenms_test_cmd_prefix} "${Python_EXECUTABLE}" -m pytest tests/integration_tests
    WORKING_DIRECTORY "${PYOPENMS_BUILD_DIR}")
  file(GLOB _pyopenms_toplevel_tests "${PYOPENMS_BUILD_DIR}/tests/test_*.py")
  if(_pyopenms_toplevel_tests)
    add_test(NAME pyopenms_feature_tests
      COMMAND ${_pyopenms_test_cmd_prefix} "${Python_EXECUTABLE}" -m pytest ${_pyopenms_toplevel_tests}
      WORKING_DIRECTORY "${PYOPENMS_BUILD_DIR}")
  endif()
endif()

message(STATUS "pyOpenMS ${PYOPENMS_PACKAGE_VERSION}: OpenMS ${OpenMS_VERSION} at ${OpenMS_SOURCE_REVISION}")
message(STATUS "Core SDK: ${OpenMS_DIR}; runtime data: ${OPENMS_SHARE_DIR}; tests: ${PYOPENMS_BUILD_TESTING}")
