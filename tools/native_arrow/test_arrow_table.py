"""Run the production Arrow helper without building the scientific bindings."""
import gc
import weakref

import pyarrow as pa
import pytest

from _arrow_table_probe import roundtrip


def test_empty_schema_and_metadata_survive():
    schema = pa.schema([("value", pa.int64()), ("label", pa.string())],
                       metadata={b"source": b"empty"})
    table = pa.Table.from_batches([], schema=schema)
    result = roundtrip(table)
    assert result.num_rows == 0
    assert result.schema.equals(schema, check_metadata=True)


class BatchStream:
    """A real C stream that forces a batch boundary after each row."""
    def __init__(self, fail_after=None):
        self.yielded = 0
        self.fail_after = fail_after
        self.schema = pa.schema([("value", pa.int64())])

    def __arrow_c_stream__(self):
        def batches():
            for index in range(4):
                if index == self.fail_after:
                    raise ValueError("controlled batch conversion failure")
                self.yielded += 1
                yield pa.record_batch([[index]], schema=self.schema)
        return pa.RecordBatchReader.from_batches(self.schema, batches()).__arrow_c_stream__()


def test_consumes_every_batch_at_conversion_boundary_and_retains_data():
    stream = BatchStream()
    result = roundtrip(stream)
    assert stream.yielded == 4  # No pre-combination can hide a batches[0] bug.
    assert result.to_pydict() == {"value": [0, 1, 2, 3]}
    owner = weakref.ref(stream)
    del stream
    gc.collect()
    assert owner() is None
    assert result.column(0).to_pylist() == [0, 1, 2, 3]


def test_failed_stream_is_reported_and_later_conversions_still_work():
    for _ in range(20):
        stream = BatchStream(fail_after=2)
        with pytest.raises(RuntimeError, match="controlled batch conversion failure"):
            roundtrip(stream)
        assert stream.yielded == 2
        owner = weakref.ref(stream)
        del stream
        gc.collect()
        assert owner() is None
        assert roundtrip(pa.table({"value": [7]})).to_pydict() == {"value": [7]}
    gc.collect()


def test_bad_protocol_does_not_reach_arrow_with_an_invalid_pointer():
    class BadStream:
        def __arrow_c_stream__(self):
            return None
    with pytest.raises(ValueError, match="PyCapsule_GetPointer"):
        roundtrip(BadStream())
    with pytest.raises(TypeError, match="Arrow C stream"):
        roundtrip(object())
