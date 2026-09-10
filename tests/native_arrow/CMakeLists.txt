cmake_minimum_required(VERSION 3.24)
project(PyOpenMSArrowBoundary LANGUAGES CXX)
find_package(Python 3.10 REQUIRED COMPONENTS Interpreter Development.Module)
execute_process(COMMAND "${Python_EXECUTABLE}" -m nanobind --cmake_dir
  OUTPUT_VARIABLE nanobind_ROOT OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
find_package(nanobind 2.10.0 EXACT CONFIG REQUIRED)
set(NB_USE_SUBMODULE_DEPS ON CACHE BOOL "Use nanobind's shipped dependencies")
find_package(Arrow CONFIG REQUIRED)
nanobind_add_module(_arrow_table_probe probe.cpp)
target_compile_features(_arrow_table_probe PRIVATE cxx_std_23)
target_link_libraries(_arrow_table_probe PRIVATE Arrow::arrow_shared)
enable_testing()
add_test(NAME arrow_stream_boundary
  COMMAND "${CMAKE_COMMAND}" -E env "PYTHONPATH=$<TARGET_FILE_DIR:_arrow_table_probe>"
    "${Python_EXECUTABLE}" -m pytest "${CMAKE_CURRENT_SOURCE_DIR}/test_arrow_table.py" -q)
