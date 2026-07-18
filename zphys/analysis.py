from __future__ import annotations

import numpy as np
from scipy import signal


def baseline_subtract(y: np.ndarray, x: np.ndarray | None = None, start: float | None = None, end: float | None = None) -> np.ndarray:
    """Subtract mean baseline over a selected time window.

    This is the first Python equivalent of base1()/baseline behavior.
    """

    y = np.asarray(y, dtype=float)
    if x is None or start is None or end is None:
        return y - np.nanmean(y)

    x = np.asarray(x, dtype=float)
    mask = (x >= start) & (x <= end)
    if not np.any(mask):
        return y - np.nanmean(y)
    return y - np.nanmean(y[mask])


def linear_baseline_subtract_2d(data: np.ndarray) -> np.ndarray:
    """Equivalent of Avg_2Dwave_BL(): linear fit baseline per column."""

    data = np.asarray(data, dtype=float)
    if data.ndim != 2:
        raise ValueError("linear_baseline_subtract_2d expects 2D data")
    x = np.arange(data.shape[0], dtype=float)
    out = np.empty_like(data)
    for col in range(data.shape[1]):
        coef = np.polyfit(x, data[:, col], deg=1)
        out[:, col] = data[:, col] - np.polyval(coef, x)
    return out


def average_sweeps(data: np.ndarray, axis: int = 1) -> np.ndarray:
    """Average sweeps stored as columns by default."""

    return np.nanmean(np.asarray(data, dtype=float), axis=axis)


def concatenate_sweeps(sweeps: list[np.ndarray]) -> np.ndarray:
    """Concatenate selected sweeps end-to-end."""

    return np.concatenate([np.asarray(s, dtype=float) for s in sweeps])


def fft_area(y: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
    """Basic FFT magnitude calculation for FFT/Area workflow."""

    y = np.asarray(y, dtype=float)
    freq = np.fft.rfftfreq(y.size, d=dt)
    amp = np.abs(np.fft.rfft(y))
    return freq, amp


def decimate(y: np.ndarray, factor: int) -> np.ndarray:
    if factor <= 1:
        return np.asarray(y, dtype=float)
    return signal.decimate(np.asarray(y, dtype=float), factor, zero_phase=True)
