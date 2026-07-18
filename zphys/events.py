from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks


def detect_spikes(
    y: np.ndarray,
    x: np.ndarray | None = None,
    threshold: float = 0.0,
    min_distance_points: int | None = None,
    polarity: str = "positive",
) -> dict[str, np.ndarray]:
    """Peak-based detector retained for compatibility."""

    y = np.asarray(y, dtype=float)
    trace = -y if polarity == "negative" else y
    peaks, props = find_peaks(trace, height=abs(threshold), distance=min_distance_points)
    times = np.asarray(x, dtype=float)[peaks] if x is not None else peaks.astype(float)
    return {
        "indices": peaks,
        "times": times,
        "amplitudes": y[peaks],
        "peak_heights": props.get("peak_heights", np.array([])),
    }


def detect_threshold_crossings(
    y: np.ndarray,
    x: np.ndarray | None = None,
    threshold: float = 0.0,
    direction: str = "auto",
    min_spacing_points: int = 1,
    smoothing_points: int = 1,
    baseline: float | None = None,
    min_peak_delta: float | None = None,
    min_event_points: int = 2,
) -> dict[str, np.ndarray]:
    """Igor-like threshold crossing detector.

    Unlike a raw crossing finder, this requires the event peak/trough to move
    meaningfully beyond the threshold. This prevents random detections exactly
    along the threshold line caused by small noise fluctuations.
    """

    raw = np.asarray(y, dtype=float)
    if raw.ndim != 1:
        raw = raw.ravel()
    if raw.size == 0:
        empty = np.array([], dtype=float)
        return {
            "indices": empty.astype(int),
            "times": empty,
            "amplitudes": empty,
            "crossing_indices": empty.astype(int),
            "crossing_times": empty,
            "direction": np.array([], dtype=str),
        }

    if x is None:
        t = np.arange(raw.size, dtype=float)
    else:
        t = np.asarray(x, dtype=float)
        if t.size != raw.size:
            t = np.arange(raw.size, dtype=float)

    smooth_n = max(1, int(round(smoothing_points or 1)))
    trace = raw if smooth_n <= 1 else uniform_filter1d(raw, size=smooth_n, mode="nearest")

    finite = trace[np.isfinite(trace)]
    if finite.size == 0:
        finite = raw[np.isfinite(raw)]
    base = float(np.nanmedian(finite)) if baseline is None and finite.size else float(baseline or 0.0)

    direction_norm = (direction or "auto").lower()
    if direction_norm in {"auto", "auto from threshold"}:
        direction_norm = "down" if threshold < base else "up"
    elif direction_norm in {"below", "negative", "downward", "below threshold / downward"}:
        direction_norm = "down"
    elif direction_norm in {"above", "positive", "upward", "above threshold / upward"}:
        direction_norm = "up"

    min_spacing = max(1, int(round(min_spacing_points or 1)))
    min_event_points = max(1, int(round(min_event_points or 1)))

    if min_peak_delta is None:
        # Adaptive default: require an event to move at least 5% of robust trace
        # spread beyond threshold, with a tiny floor. This is intentionally
        # conservative enough to reject threshold-line chatter.
        p1, p99 = np.nanpercentile(raw[np.isfinite(raw)], [1, 99]) if np.any(np.isfinite(raw)) else (0.0, 1.0)
        robust_range = abs(float(p99 - p1))
        min_peak_delta = max(robust_range * 0.05, np.finfo(float).eps * 100)

    if direction_norm == "down":
        crossings = np.where((trace[:-1] >= threshold) & (trace[1:] < threshold))[0] + 1
    else:
        crossings = np.where((trace[:-1] <= threshold) & (trace[1:] > threshold))[0] + 1

    event_indices: list[int] = []
    crossing_indices: list[int] = []
    last_index = -10**12

    for c in crossings:
        if c - last_index < min_spacing:
            continue

        # Search window: at least min_spacing points, but stop at recrossing when possible.
        end = min(raw.size, c + max(min_spacing, min_event_points + 1, 2))
        if direction_norm == "down":
            recross = np.where(trace[c:end] >= threshold)[0]
            if recross.size and recross[0] >= min_event_points:
                end = c + int(recross[0])
            if end - c < min_event_points:
                continue
            local = c + int(np.nanargmin(raw[c:end]))
            peak_delta = threshold - raw[local]
            if peak_delta < min_peak_delta:
                continue
        else:
            recross = np.where(trace[c:end] <= threshold)[0]
            if recross.size and recross[0] >= min_event_points:
                end = c + int(recross[0])
            if end - c < min_event_points:
                continue
            local = c + int(np.nanargmax(raw[c:end]))
            peak_delta = raw[local] - threshold
            if peak_delta < min_peak_delta:
                continue

        event_indices.append(local)
        crossing_indices.append(c)
        last_index = local

    idx = np.asarray(event_indices, dtype=int)
    cidx = np.asarray(crossing_indices, dtype=int)

    return {
        "indices": idx,
        "times": t[idx] if idx.size else np.array([], dtype=float),
        "amplitudes": raw[idx] if idx.size else np.array([], dtype=float),
        "crossing_indices": cidx,
        "crossing_times": t[cidx] if cidx.size else np.array([], dtype=float),
        "direction": np.asarray([direction_norm] * idx.size),
    }


def inter_spike_intervals(spike_times: np.ndarray) -> np.ndarray:
    return np.diff(np.asarray(spike_times, dtype=float))


def instantaneous_frequency(spike_times: np.ndarray) -> np.ndarray:
    isi = inter_spike_intervals(spike_times)
    return np.divide(1.0, isi, out=np.full_like(isi, np.nan), where=isi != 0)


def vector_strength(spike_times: np.ndarray, frequency_hz: float) -> float:
    spike_times = np.asarray(spike_times, dtype=float)
    if spike_times.size == 0 or frequency_hz <= 0:
        return float("nan")
    phases = 2 * np.pi * frequency_hz * spike_times
    return float(np.abs(np.mean(np.exp(1j * phases))))
