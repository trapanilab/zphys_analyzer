from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np


@dataclass
class FieldPotentialSettings:
    stimulus_onset_s: float = 0.050
    stimulus_length_s: float = 0.050
    search_offset_s: float = 0.001
    rms_window_s: float = 0.050
    rms_sigma_multiplier: float = 0.200
    baseline_subtract: bool = True


@dataclass
class FieldPotentialResult:
    source: str = ""
    sweep: int = 0
    stim_to_peak_s: float = math.nan
    fp_latency_s: float = math.nan
    fp_amplitude: float = math.nan
    fp_length_s: float = math.nan
    onset_time_s: float = math.nan
    onset_y: float = math.nan
    peak_time_s: float = math.nan
    peak_y: float = math.nan
    trough_time_s: float = math.nan
    trough_y: float = math.nan
    return_time_s: float = math.nan
    status: str = ""
    display_name: str = ""


def _finite(v: float) -> bool:
    return bool(np.isfinite(v))


def _first_point_at_or_after(x: np.ndarray, target: float) -> int:
    finite = np.flatnonzero(np.isfinite(x) & (x >= target))
    if finite.size:
        return int(finite[0])
    finite = np.flatnonzero(np.isfinite(x))
    return int(finite[-1]) if finite.size else -1


def _closest_x_point(x: np.ndarray, target: float) -> int:
    finite = np.flatnonzero(np.isfinite(x))
    if not finite.size:
        return -1
    idx = finite[int(np.nanargmin(np.abs(x[finite] - target)))]
    return int(idx)


def preprocess_sweep(y: np.ndarray, x: np.ndarray, settings: FieldPotentialSettings) -> tuple[np.ndarray, str]:
    y = np.asarray(y, dtype=float).copy()
    x = np.asarray(x, dtype=float)
    if not settings.baseline_subtract:
        return y, ""
    valid = np.flatnonzero(np.isfinite(x) & np.isfinite(y))
    if not valid.size:
        return y, "baseline failed: no finite points; "
    last = int(valid[-1])
    final_time = float(x[last])
    start_time = final_time - float(settings.rms_window_s)
    mask = np.isfinite(x) & np.isfinite(y) & (x >= start_time) & (x <= final_time)
    if not np.any(mask):
        return y, "baseline failed: empty final RMS window; "
    y -= float(np.nanmean(y[mask]))
    return y, ""


def calculate_onset_point(y: np.ndarray, x: np.ndarray, stimulus_onset: float, peak_point: int, trough_point: int) -> int:
    if x[peak_point] < x[trough_point]:
        first_extremum = peak_point
    elif x[trough_point] < x[peak_point]:
        first_extremum = trough_point
    elif abs(y[peak_point]) >= abs(y[trough_point]):
        first_extremum = peak_point
    else:
        first_extremum = trough_point

    first_stim = _first_point_at_or_after(x, stimulus_onset)
    if first_stim < 0:
        return -1
    half_y = 0.5 * float(y[first_extremum])
    half_time = math.nan

    for i in range(first_extremum - 1, first_stim - 1, -1):
        if not (np.isfinite(y[i]) and np.isfinite(y[i + 1]) and np.isfinite(x[i]) and np.isfinite(x[i + 1])):
            continue
        y1 = float(y[i])
        y2 = float(y[i + 1])
        if half_y >= min(y1, y2) and half_y <= max(y1, y2):
            if y2 == y1:
                half_time = float(x[i])
            else:
                half_time = float(x[i]) + (half_y - y1) * (float(x[i + 1]) - float(x[i])) / (y2 - y1)
            break

    if not np.isfinite(half_time):
        return -1

    extremum_time = float(x[first_extremum])
    delta_x = abs(extremum_time - half_time)
    onset_time = half_time - delta_x
    onset_time = max(float(stimulus_onset), min(extremum_time, onset_time))
    onset_point = _closest_x_point(x, onset_time)
    if onset_point < 0:
        return -1
    return int(max(first_stim, min(first_extremum, onset_point)))


def find_rms_return_point(
    y: np.ndarray,
    x: np.ndarray,
    peak_point: int,
    last_valid_point: int,
    rms_window: float,
    rms_sigma_multiplier: float,
) -> int:
    last_time = float(x[last_valid_point])
    reference_start = last_time - float(rms_window)
    ref_mask = (
        np.isfinite(x[: last_valid_point + 1])
        & np.isfinite(y[: last_valid_point + 1])
        & (x[: last_valid_point + 1] >= reference_start)
        & (x[: last_valid_point + 1] <= last_time)
    )
    ref = y[: last_valid_point + 1][ref_mask]
    if ref.size < 2:
        return -2
    reference_rms = float(np.sqrt(np.mean(ref * ref)))
    reference_sdev = float(np.std(ref, ddof=1))
    allowed = float(rms_sigma_multiplier) * reference_sdev

    window_end = peak_point - 1
    window_indices: list[int] = []
    window_sum_squares = 0.0

    for candidate_start in range(int(peak_point), int(last_valid_point) + 1):
        if candidate_start > peak_point:
            prev = candidate_start - 1
            if prev in window_indices:
                window_indices.remove(prev)
                if np.isfinite(y[prev]):
                    window_sum_squares -= float(y[prev] * y[prev])

        if not (np.isfinite(x[candidate_start]) and np.isfinite(y[candidate_start])):
            continue
        candidate_end_time = float(x[candidate_start]) + float(rms_window)
        if candidate_end_time > last_time:
            break

        while True:
            nxt = window_end + 1
            if nxt > last_valid_point:
                break
            if not np.isfinite(x[nxt]):
                window_end = nxt
                continue
            if float(x[nxt]) > candidate_end_time:
                break
            window_end = nxt
            if np.isfinite(y[nxt]):
                window_indices.append(nxt)
                window_sum_squares += float(y[nxt] * y[nxt])

        count = len(window_indices)
        if count <= 0:
            continue
        candidate_rms = math.sqrt(max(0.0, window_sum_squares) / count)
        if abs(candidate_rms - reference_rms) <= allowed:
            return int(candidate_start)
    return -1


def analyze_field_potential(
    x: np.ndarray,
    y: np.ndarray,
    settings: FieldPotentialSettings,
    source: str = "",
    sweep: int = 0,
    display_name: str = "",
) -> FieldPotentialResult:
    x = np.asarray(x, dtype=float)
    y0 = np.asarray(y, dtype=float)
    result = FieldPotentialResult(source=source, sweep=int(sweep), display_name=display_name)

    if x.ndim != 1 or y0.ndim != 1:
        result.status = "ERROR: input must be 1D"
        return result
    if x.size != y0.size or x.size < 2:
        result.status = "ERROR: X and Y lengths do not match"
        return result

    y, baseline_warning = preprocess_sweep(y0, x, settings)
    warning = baseline_warning

    finite_x = np.flatnonzero(np.isfinite(x))
    if finite_x.size < 2:
        result.status = "ERROR: insufficient valid X values"
        return result
    valid_x = x[finite_x]
    if np.any(np.diff(valid_x) <= 0):
        result.status = "ERROR: X values are not increasing"
        return result
    last_valid = int(finite_x[-1])

    search_start = float(settings.stimulus_onset_s) + float(settings.search_offset_s)
    search_end = float(settings.stimulus_onset_s) + float(settings.stimulus_length_s) - float(settings.search_offset_s)
    if search_end <= search_start:
        result.status = "ERROR: derived peak/trough search interval is invalid"
        return result
    if settings.rms_window_s <= 0 or settings.rms_sigma_multiplier < 0:
        result.status = "ERROR: invalid RMS settings"
        return result

    search_mask = np.isfinite(x) & np.isfinite(y) & (x >= search_start) & (x <= search_end)
    search_idx = np.flatnonzero(search_mask)
    if not search_idx.size:
        result.status = "ERROR: no valid peak/trough data in derived search interval"
        return result

    peak_point = int(search_idx[int(np.nanargmax(y[search_idx]))])
    trough_point = int(search_idx[int(np.nanargmin(y[search_idx]))])

    result.peak_time_s = float(x[peak_point])
    result.peak_y = float(y[peak_point])
    result.trough_time_s = float(x[trough_point])
    result.trough_y = float(y[trough_point])
    result.stim_to_peak_s = result.peak_time_s - float(settings.stimulus_onset_s)
    result.fp_amplitude = result.peak_y - result.trough_y

    onset_point = calculate_onset_point(y, x, float(settings.stimulus_onset_s), peak_point, trough_point)
    if onset_point < 0:
        onset_point = _first_point_at_or_after(x, float(settings.stimulus_onset_s))
        warning += "onset extrapolation failed; used stimulus onset; "
    if onset_point < 0:
        result.status = "ERROR: failed to find onset point"
        return result

    result.onset_time_s = float(x[onset_point])
    result.onset_y = float(y[onset_point])
    result.fp_latency_s = result.onset_time_s - float(settings.stimulus_onset_s)

    return_point = find_rms_return_point(
        y, x, peak_point, last_valid, float(settings.rms_window_s), float(settings.rms_sigma_multiplier)
    )
    if return_point == -2:
        warning += "final RMS reference window invalid; "
    if return_point >= 0:
        result.return_time_s = float(x[return_point])
        result.fp_length_s = result.return_time_s - result.onset_time_s
    else:
        warning += "no RMS-based return found; "

    if result.onset_time_s < float(settings.stimulus_onset_s):
        warning += "FP onset precedes stimulus; "
    if np.isfinite(result.return_time_s) and result.return_time_s < result.onset_time_s:
        warning += "return precedes FP onset; "

    result.status = "OK" if not warning else "WARNING: " + warning
    return result


def result_to_row(result: FieldPotentialResult) -> dict:
    return {
        "source": result.source,
        "sweep": result.sweep,
        "stim_to_peak_s": result.stim_to_peak_s,
        "fp_latency_s": result.fp_latency_s,
        "fp_amplitude": result.fp_amplitude,
        "fp_length_s": result.fp_length_s,
        "onset_time_s": result.onset_time_s,
        "onset_y": result.onset_y,
        "peak_time_s": result.peak_time_s,
        "peak_y": result.peak_y,
        "trough_time_s": result.trough_time_s,
        "trough_y": result.trough_y,
        "return_time_s": result.return_time_s,
        "status": result.status,
        "display_name": result.display_name,
    }
