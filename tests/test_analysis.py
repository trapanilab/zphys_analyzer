import numpy as np

from zphys.analysis import baseline_subtract, linear_baseline_subtract_2d
from zphys.events import vector_strength


def test_baseline_subtract():
    y = np.array([1, 2, 3], dtype=float)
    out = baseline_subtract(y)
    assert np.isclose(out.mean(), 0)


def test_linear_baseline_subtract_2d():
    x = np.arange(10)
    data = np.column_stack([x + 1, 2*x + 3])
    out = linear_baseline_subtract_2d(data)
    assert np.allclose(out, 0, atol=1e-12)


def test_vector_strength():
    assert np.isfinite(vector_strength(np.array([0.0, 0.1, 0.2]), 10))
