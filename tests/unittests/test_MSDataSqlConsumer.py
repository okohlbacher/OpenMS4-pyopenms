"""MSDataSqlConsumer writes sqMass in batches; finalize() makes the file complete while the
consumer is still alive, and the destructor's own finalize must not duplicate records."""

import gc

import pytest

import pyopenms


def test_finalize_round_trip(tmp_path):
    path = str(tmp_path / "out.sqMass")
    # batch of 2 forces a mid-stream flush
    consumer = pyopenms.MSDataSqlConsumer(path, 0, 2, True, False, 1e-4)
    for i in range(3):
        s = pyopenms.MSSpectrum()
        s.setRT(10.0 + i)
        s.setMSLevel(1)
        s.setNativeID("scan=%d" % (i + 1))
        s.set_peaks(([100.0 + i, 200.0], [1.0, 2.0]))
        consumer.consumeSpectrum(s)
    consumer.finalize()

    def load():
        return pyopenms.SqMassFile().load(path)

    exp = load()
    assert exp.getNrSpectra() == 3
    assert [s.getRT() for s in exp.getSpectra()] == pytest.approx([10.0, 11.0, 12.0])
    mz, intensity = exp.getSpectrum(2).get_peaks()
    assert list(mz) == pytest.approx([102.0, 200.0])
    assert list(intensity) == pytest.approx([1.0, 2.0])

    del consumer
    gc.collect()
    assert load().getNrSpectra() == 3
