// Copyright (c) 2002-present, OpenMS Inc. -- EKU Tuebingen, ETH Zurich, and FU Berlin
// SPDX-License-Identifier: BSD-3-Clause
// $Maintainer: OpenMS Team $
#pragma once

#include <arrow/api.h>
#include <arrow/c/abi.h>
#include <arrow/c/bridge.h>
#include <cstdlib>
#include <cstring>
#include <nanobind/nanobind.h>

namespace PyOpenMS
{
// Helper: RAII guard for malloc'd Arrow structs
struct ArrowGuard
{
  ArrowSchema* schema;
  ArrowArray* array;

  ArrowGuard(): schema(static_cast<ArrowSchema*>(std::malloc(sizeof(ArrowSchema)))), array(static_cast<ArrowArray*>(std::malloc(sizeof(ArrowArray))))
  {
    if (! schema || ! array)
    {
      std::free(schema);
      std::free(array);
      throw std::bad_alloc();
    }
    std::memset(schema, 0, sizeof(ArrowSchema));
    std::memset(array, 0, sizeof(ArrowArray));
  }

  ~ArrowGuard()
  {
    if (schema)
    {
      if (schema->release) schema->release(schema);
      std::free(schema);
    }
    if (array)
    {
      if (array->release) array->release(array);
      std::free(array);
    }
  }

  // Release ownership (after PyArrow takes over)
  void release()
  {
    // PyArrow now owns the Arrow data; just free the malloc'd structs
    // without calling the release callbacks
    std::free(schema);
    std::free(array);
    schema = nullptr;
    array = nullptr;
  }

  ArrowGuard(const ArrowGuard&) = delete;
  ArrowGuard& operator=(const ArrowGuard&) = delete;
};

// Import a filled ArrowSchema+ArrowArray into a PyArrow Table
inline nanobind::object import_to_pyarrow(ArrowGuard& guard)
{
  nanobind::module_ pa = nanobind::module_::import_("pyarrow");

  // _import_from_c expects integer addresses
  auto batch = pa.attr("RecordBatch").attr("_import_from_c")(reinterpret_cast<uintptr_t>(guard.array), reinterpret_cast<uintptr_t>(guard.schema));

  // PyArrow now owns the Arrow data
  guard.release();

  return pa.attr("Table").attr("from_batches")(nanobind::make_tuple(batch));
}

// Convert a C++ arrow::Table to a PyArrow Table via the C Data Interface.
// The table is combined into a single RecordBatch, exported to C structs,
// then imported by PyArrow. Combining chunks may copy buffers; the C Data
// Interface transfers Arrow buffer ownership without another data copy.
inline nanobind::object table_to_pyarrow(const std::shared_ptr<arrow::Table>& table)
{
  if (! table) throw std::runtime_error("Arrow export returned null table");

  auto batch_result = table->CombineChunksToBatch();
  if (! batch_result.ok()) throw std::runtime_error("Failed to combine Arrow table chunks: " + batch_result.status().ToString());

  auto batch = batch_result.ValueOrDie();

  ArrowGuard guard;
  auto schema_status = arrow::ExportSchema(*batch->schema(), guard.schema);
  if (! schema_status.ok()) throw std::runtime_error("Failed to export Arrow schema: " + schema_status.ToString());

  auto array_status = arrow::ExportRecordBatch(*batch, guard.array);
  if (! array_status.ok()) throw std::runtime_error("Failed to export Arrow record batch: " + array_status.ToString());

  return import_to_pyarrow(guard);
}

// Import every batch through Arrow's standard stream protocol, including a
// zero-row stream's schema. No combine_chunks allocation is required here.
inline std::shared_ptr<arrow::Table> pyarrow_to_table(nanobind::object table)
{
  if (! nanobind::hasattr(table, "__arrow_c_stream__")) throw nanobind::type_error("Expected a pyarrow.Table or Arrow C stream provider");
  nanobind::object capsule = table.attr("__arrow_c_stream__")();
  auto* stream = static_cast<ArrowArrayStream*>(PyCapsule_GetPointer(capsule.ptr(), "arrow_array_stream"));
  if (! stream) throw nanobind::python_error();

  // Import moves the stream to the reader; capsule destruction can then free
  // the original struct. The reader owns release callbacks on all error paths.
  auto reader = arrow::ImportRecordBatchReader(stream);
  if (! reader.ok()) throw std::runtime_error("Failed to import Arrow stream: " + reader.status().ToString());
  auto result = (*reader)->ToTable();
  if (! result.ok()) throw std::runtime_error("Failed to read Arrow stream: " + result.status().ToString());
  return *result;
}
} // namespace PyOpenMS
