// SPDX-License-Identifier: BSD-3-Clause
#include "../../bindings/arrow_table.h"

NB_MODULE(_arrow_table_probe, m)
{
  m.def("roundtrip", [](nanobind::object table) { return PyOpenMS::table_to_pyarrow(PyOpenMS::pyarrow_to_table(table)); });
}
