// pyOpenMS nanobind bindings
// Main module - placeholder, actual bindings in _pyopenms_<domain> modules

#include <OpenMS/CONCEPT/VersionInfo.h>
#include <OpenMS/SYSTEM/File.h>
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include "runtime_abi.h"

namespace nb = nanobind;

NB_MODULE(_pyopenms, m)
{
  m.doc() = "pyOpenMS: Python bindings for OpenMS (nanobind)\n"
            "Note: Import pyopenms instead for all classes.";
  m.def("_core_build_info", &OpenMS::VersionInfo::getBuildInfo);
  m.def("_core_source_revision", &OpenMS::VersionInfo::getSourceRevision);
  m.def("_core_source_dirty", &OpenMS::VersionInfo::isSourceDirty);
  m.def("_core_data_path", &OpenMS::File::getOpenMSDataPath);
}
