from __future__ import annotations

from pathlib import Path
import re
import contextlib
import io
from typing import Any

import numpy as np
import pandas as pd

from .models import Recording, Series, Sweep


class LoaderError(RuntimeError):
    pass


def load_csv(path: str | Path) -> Recording:
    """Load a CSV file into one or more sweeps.

    This is the Python equivalent of Import_CSV_File().
    Each numeric column becomes a sweep. If the first column looks like time,
    it is used as the x-axis for the remaining columns.
    """

    path = Path(path)
    df = pd.read_csv(path)
    numeric = df.select_dtypes(include=["number"])
    if numeric.empty:
        raise LoaderError(f"No numeric columns found in {path}")

    columns = list(numeric.columns)
    x = None
    y_columns = columns
    first_name = str(columns[0]).lower()
    if first_name in {"time", "t", "sec", "seconds", "x"} and len(columns) > 1:
        x = numeric[columns[0]].to_numpy(dtype=float)
        y_columns = columns[1:]

    sweeps = [
        Sweep(
            y=numeric[col].to_numpy(dtype=float),
            x=x,
            name=str(col),
            metadata={"column": str(col)},
        )
        for col in y_columns
    ]
    return Recording(path=path, source_format="csv", sweeps=sweeps, metadata={"columns": columns})


def load_abf(path: str | Path) -> Recording:
    """Load Axon ABF files using pyABF."""

    path = Path(path)
    try:
        import pyabf
    except ImportError as exc:
        raise LoaderError("Install pyabf to load .abf files: pip install pyabf") from exc

    abf = pyabf.ABF(str(path))
    sweeps: list[Sweep] = []
    for sweep_index in range(abf.sweepCount):
        abf.setSweep(sweep_index)
        sweeps.append(
            Sweep(
                y=np.asarray(abf.sweepY, dtype=float).copy(),
                x=np.asarray(abf.sweepX, dtype=float).copy(),
                name=f"sweep_{sweep_index + 1}",
                units=getattr(abf, "sweepUnitsY", ""),
                metadata={"sweep_index": sweep_index},
            )
        )

    return Recording(
        path=path,
        source_format="abf",
        sweeps=sweeps,
        metadata={
            "abf_id": getattr(abf, "abfID", ""),
            "protocol": getattr(abf, "protocol", ""),
            "sweep_count": getattr(abf, "sweepCount", len(sweeps)),
            "channel_count": getattr(abf, "channelCount", None),
        },
    )


def load_pxp(path: str | Path) -> Recording:
    """Load Igor/SutterPatch PXP files into a normalized Recording.

    SutterPatch stores data under root:SutterPatch:Data. Routine waves are
    named like R15_S1_Action_Light20Hz and are 2D arrays where rows are time
    points and columns are sweeps. This loader maps each such wave to a Series
    and also exposes each column as a Sweep for simple GUI navigation.

    Some SutterPatch PXP files contain records that igor2 cannot construct even
    though the rest of the file is valid. The loader first tries normal
    igor2.packed.load(), then falls back to a tolerant record parser that skips
    malformed records after their bytes have been read.
    """

    path = Path(path)
    filesystem, parse_report = _load_pxp_filesystem_tolerant(path)
    data_folder = _find_sutterpatch_data_folder(filesystem)
    if data_folder is None:
        return _load_generic_pxp_waves(path, filesystem, parse_report)

    experiment_structure = _wave_to_text_table(data_folder.get(b"ExperimentStructure") or data_folder.get("ExperimentStructure"))

    series: list[Series] = []
    # S2 is a simultaneously recorded input signal, not necessarily the output stimulus.
    # Actual stimulus/output previews are collected separately from SutterPatch WavePreview waves.
    stimulus: list[Sweep] = []
    flat_sweeps: list[Sweep] = []

    for raw_name, value in data_folder.items():
        name = _decode_key(raw_name)
        if name == "ExperimentStructure":
            continue
        arr = _wave_to_array(value)
        if arr is None or arr.size == 0 or not np.issubdtype(arr.dtype, np.number):
            continue

        arr = np.asarray(arr, dtype=float)
        if arr.ndim == 1:
            arr = arr[:, None]
        elif arr.ndim > 2:
            continue

        wave_header = _wave_header(value)
        sampling_interval = _sampling_interval_seconds(wave_header)
        units = _decode_units(wave_header.get("dataUnits", b""))

        parsed = _parse_sutter_series_name(name)
        note = _wave_note(value)

        note_fields = _parse_sutter_note_fields(note)
        s = Series(
            name=name,
            data=arr,
            sampling_interval=sampling_interval,
            units=units,
            metadata={
                "igor_name": name,
                "routine_number": parsed.get("routine_number"),
                "signal_number": parsed.get("signal_number"),
                "routine_name": parsed.get("routine_name"),
                "signal_name": note_fields.get("SignalName"),
                "note_fields": note_fields,
                "note": note,
                "shape": tuple(arr.shape),
            },
        )
        series.append(s)

        for i in range(s.sweep_count):
            sweep = s.sweep(i)
            flat_sweeps.append(sweep)

    if not series:
        raise LoaderError("PXP was readable, but no numeric SutterPatch data waves were found.")

    series.sort(key=lambda s: (
        s.metadata.get("routine_number") or 10**9,
        s.metadata.get("signal_number") or 10**9,
        s.name,
    ))

    stimulus_series = _collect_sutterpatch_stimulus_preview_series(filesystem, series)
    # SutterPatch support confirmed that AppControl objects are execution state
    # and Data:Routines is an encoded routine copy that currently can only be
    # regenerated inside SutterPatch. Do not synthesize output waveforms from
    # routine names or encoded routine copies here. Only expose waveforms that
    # are actually stored/accessibly present in the PXP file.
    for stim_series in stimulus_series:
        stimulus.extend(stim_series.sweep(i) for i in range(stim_series.sweep_count))

    return Recording(
        path=path,
        source_format="pxp",
        sweeps=flat_sweeps,
        stimulus=stimulus,
        series=series,
        metadata={
            "loader": "igor2+tolerant_sutterpatch",
            "parse_report": parse_report,
            "experiment_structure": experiment_structure,
            "series_count": len(series),
            "sweep_count": len(flat_sweeps),
            "stimulus_series": stimulus_series,
            "stimulus_series_count": len(stimulus_series),
        },
    )


def load_ibw(path: str | Path) -> Recording:
    path = Path(path)
    try:
        from igor2 import binarywave
    except ImportError as exc:
        raise LoaderError("Install igor2 to load .ibw files: pip install igor2") from exc

    data = binarywave.load(str(path))
    arr = _wave_to_array(data)
    if arr is None:
        raise LoaderError(f"No numeric data found in {path}")

    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 1:
        sweeps = [Sweep(y=arr, name=path.stem)]
        series = [Series(name=path.stem, data=arr[:, None])]
    else:
        sweeps = [Sweep(y=arr[:, col], name=f"{path.stem}_{col + 1}") for col in range(arr.shape[1])]
        series = [Series(name=path.stem, data=arr)]
    return Recording(path=path, source_format="ibw", sweeps=sweeps, series=series)


def load_any(path: str | Path) -> Recording:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return load_csv(path)
    if suffix == ".abf":
        return load_abf(path)
    if suffix == ".pxp":
        return load_pxp(path)
    if suffix == ".ibw":
        return load_ibw(path)
    raise LoaderError(f"Unsupported file type: {suffix}")


def _load_pxp_filesystem_tolerant(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        from igor2 import packed
    except ImportError as exc:
        raise LoaderError("Install igor2 to load .pxp files: pip install igor2") from exc

    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            records, filesystem = packed.load(str(path))
        return filesystem, {"mode": "normal", "records_ok": len(records), "records_skipped": 0, "skipped": []}
    except Exception as first_error:
        pass

    # Fallback: adapted from igor2.packed.load(), but continue after malformed records.
    records = []
    skipped = []
    initial_byte_order = "="
    byte_order = None

    with open(path, "rb") as f:
        index = 0
        while True:
            offset = f.tell()
            header_struct = packed.setup_packed_file_record_header(byte_order=initial_byte_order)
            b = bytes(f.read(header_struct.size))
            if not b:
                break
            if len(b) < header_struct.size:
                skipped.append({"index": index, "offset": offset, "reason": "short header"})
                break

            header = header_struct.unpack_from(b)
            if header["version"] and not byte_order:
                need_to_reorder = packed._need_to_reorder_bytes(header["version"])
                byte_order = initial_byte_order = packed._byte_order(need_to_reorder)
                if need_to_reorder:
                    header_struct = packed.setup_packed_file_record_header(byte_order=byte_order)
                    header = header_struct.unpack_from(b)

            n_bytes = int(header["numDataBytes"])
            data = bytes(f.read(n_bytes))
            if len(data) < n_bytes:
                skipped.append({"index": index, "offset": offset, "reason": "short record"})
                break

            record_type_id = int(header["recordType"] & packed.PACKEDRECTYPE_MASK)
            record_type = packed._RECORD_TYPE.get(record_type_id, packed._UnknownRecord)
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    records.append(record_type(header, data, byte_order=byte_order))
            except Exception as exc:
                skipped.append(
                    {
                        "index": index,
                        "offset": offset,
                        "record_type": record_type_id,
                        "num_data_bytes": n_bytes,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            index += 1

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        filesystem = packed._build_filesystem(records)
    return filesystem, {"mode": "tolerant", "records_ok": len(records), "records_skipped": len(skipped), "skipped": skipped}


def _find_sutterpatch_data_folder(filesystem: dict[str, Any]) -> dict[str, Any] | None:
    root = filesystem.get("root") or filesystem.get(b"root") or filesystem
    sp = root.get(b"SutterPatch") if isinstance(root, dict) else None
    if sp is None and isinstance(root, dict):
        sp = root.get("SutterPatch")
    if not isinstance(sp, dict):
        return None
    data = sp.get(b"Data") or sp.get("Data")
    return data if isinstance(data, dict) else None


def _collect_sutterpatch_stimulus_preview_series(filesystem: dict[str, Any], recorded_series: list[Series]) -> list[Series]:
    """Collect SutterPatch output/stimulus preview waves.

    Recorded S1/S2 waves are in root:SutterPatch:Data, but SutterPatch also
    keeps output/stimulus waveform previews elsewhere, commonly under
    AppControl/Routines/WavePreview.  These are not sweeps recorded from input
    channels; they are command/output previews such as DigOUT, StimOUT, AuxOUT.
    """
    waves: list[tuple[str, Any]] = []
    _collect_igor_waves(filesystem, waves)

    out: list[Series] = []
    seen: set[str] = set()
    default_dt = None
    for s in recorded_series:
        if s.sampling_interval and s.sampling_interval > 0:
            default_dt = s.sampling_interval
            break

    for name, wave_obj in waves:
        lname = name.lower()
        note = _wave_note(wave_obj)
        note_fields = _parse_sutter_note_fields(note)
        signal_name = str(note_fields.get("SignalName") or "")
        signal_l = signal_name.lower()

        is_preview_path = "wavepreview" in lname
        looks_like_output = any(token in signal_l for token in ("stim", "digout", "auxout", "ttl", "dac", "out"))
        looks_like_name = any(token in lname for token in ("stim", "digout", "auxout", "wavepreview", "ttl", "dac"))
        if not (is_preview_path and (looks_like_output or looks_like_name)):
            continue

        arr = _wave_to_array(wave_obj)
        if arr is None or arr.size == 0 or not np.issubdtype(arr.dtype, np.number):
            continue
        arr = np.asarray(arr, dtype=float)
        if arr.ndim == 1:
            arr = arr[:, None]
        elif arr.ndim != 2:
            continue

        key = f"{name}:{arr.shape}"
        if key in seen:
            continue
        seen.add(key)

        header = _wave_header(wave_obj)
        dt = _sampling_interval_seconds(header) or default_dt
        units = _decode_units(header.get("dataUnits", b"")) or signal_name or "stim"
        label = name.split("/")[-1]
        if signal_name:
            label = f"{label} ({signal_name})"
        out.append(Series(
            name=label,
            data=arr,
            sampling_interval=dt,
            units=units,
            metadata={
                "igor_name": name,
                "stimulus_preview": True,
                "signal_name": signal_name or None,
                "note": note,
                "note_fields": note_fields,
                "shape": tuple(arr.shape),
            },
        ))

    out.sort(key=lambda s: (abs(s.point_count - (recorded_series[0].point_count if recorded_series else s.point_count)), s.name))
    return out


def _synthesize_fjet_sine_stimulus_series(recorded_series: list[Series], existing_stimulus: list[Series]) -> list[Series]:
    """Reconstruct sine command previews for Fjet routines when analog previews are missing/flat.

    Older SutterPatch files can contain a flat zero StimOUT preview plus digital
    DigOUT wave previews, while the actual routine name indicates a sine command
    such as Action_Fjet20Hz. In that situation the digital word is not the
    intended analog stimulus. This creates a normalized sine preview so display
    and overlay show the intended stimulus shape.
    """
    if not recorded_series:
        return []

    # If there is already a non-flat analog output preview, trust it.
    for stim in existing_stimulus or []:
        name = f"{stim.name} {stim.metadata.get('signal_name') or ''}".lower()
        if not any(tok in name for tok in ("stimout", "auxout", "dac", "analog")):
            continue
        try:
            arr = np.asarray(stim.data, dtype=float)
            finite = arr[np.isfinite(arr)]
            if finite.size and float(np.nanmax(finite)) != float(np.nanmin(finite)):
                return []
        except Exception:
            pass

    out: list[Series] = []
    seen: set[tuple[Any, str, int]] = set()
    for s in recorded_series:
        routine_name = str(s.metadata.get("routine_name") or s.name)
        haystack = routine_name.lower()
        if "fjet" not in haystack:
            continue
        m = re.search(r"(\d+(?:\.\d+)?)\s*hz", haystack)
        if not m:
            continue
        freq_hz = float(m.group(1))
        rnum = s.metadata.get("routine_number")
        key = (rnum, routine_name, int(s.point_count))
        # One sine preview per routine, not one per S1/S2.
        if key in seen:
            continue
        seen.add(key)

        dt = s.sampling_interval or 1.0
        n = int(s.point_count)
        if n <= 1:
            continue
        t = np.arange(n, dtype=float) * dt
        # Normalized amplitude: the exact analog command amplitude is not
        # recoverable from these flat-preview files, but right-axis overlay makes
        # shape/timing visible independent of recording units.
        y = np.sin(2.0 * np.pi * freq_hz * t)
        label = f"Synthetic Fjet sine R{rnum if rnum is not None else '?'} ({freq_hz:g} Hz)"
        out.append(Series(
            name=label,
            data=y[:, None],
            sampling_interval=dt,
            units="normalized",
            metadata={
                "stimulus_preview": True,
                "synthetic_stimulus": True,
                "synthetic_kind": "fjet_sine",
                "signal_name": "Fjet sine",
                "routine_number": rnum,
                "routine_name": routine_name,
                "frequency_hz": freq_hz,
                "source": "routine name fallback because stored analog preview was flat/missing",
            },
        ))

    out.sort(key=lambda s: (s.metadata.get("routine_number") or 10**9, s.name))
    return out


def _synthesize_stimulus_series_from_sutterpatch_metadata(filesystem: dict[str, Any], recorded_series: list[Series]) -> list[Series]:
    """Create fallback stimulus pulses when SutterPatch did not save preview waves.

    Some SutterPatch files, including data from certain amplifier/acquisition
    setups, do not contain AppControl/Routines/WavePreview waves. The routine
    metadata may still encode enough information for a useful stimulus preview:
    routine names such as ``AMCM_50msflash_5V`` and encrypted routine text
    containing output channel labels such as ``LED_TRIG1``.

    This fallback deliberately marks the generated series as synthetic so the GUI
    can report that it is a reconstructed pulse, not a stored command waveform.
    """
    if not recorded_series:
        return []

    data_folder = _find_sutterpatch_data_folder(filesystem)
    if not isinstance(data_folder, dict):
        return []

    routines_folder = data_folder.get("Routines") or data_folder.get(b"Routines")
    routine_text_by_number: dict[int, str] = {}
    if isinstance(routines_folder, dict):
        for raw_name, wave_obj in routines_folder.items():
            name = _decode_key(raw_name)
            m = re.match(r"R(\d+)_", name)
            if not m:
                continue
            arr = _wave_to_array(wave_obj)
            text_parts: list[str] = []
            if arr is not None:
                for item in np.asarray(arr).ravel():
                    if isinstance(item, bytes):
                        text_parts.append(item.decode("latin1", "ignore"))
                    else:
                        text_parts.append(str(item))
            note = _wave_note(wave_obj)
            if note:
                text_parts.append(note)
            routine_text_by_number[int(m.group(1))] = "\n".join(text_parts)

    out: list[Series] = []
    seen: set[tuple[int | None, str, int]] = set()
    for s in recorded_series:
        rnum = s.metadata.get("routine_number")
        rname = str(s.metadata.get("routine_name") or s.name)
        key = (rnum, rname, s.point_count)
        # Only synthesize one stimulus per routine, not once for S1 and S2.
        if key in seen:
            continue
        seen.add(key)

        params = _infer_pulse_from_routine_metadata(rname, routine_text_by_number.get(rnum or -1, ""))
        if params is None:
            continue

        dt = s.sampling_interval or 1.0
        n = int(s.point_count)
        if n <= 1:
            continue
        duration_s = params.get("duration_s", 0.05)
        amplitude = params.get("amplitude", 1.0)
        onset_s = params.get("onset_s")
        if onset_s is None:
            # Place fallback pulses near the middle of the sweep so they are
            # visible without pretending to know exact command timing.
            total_s = n * dt
            onset_s = max(0.0, min(total_s - duration_s, 0.5 * total_s - 0.5 * duration_s))

        y = np.zeros(n, dtype=float)
        start = max(0, min(n - 1, int(round(onset_s / dt))))
        stop = max(start + 1, min(n, int(round((onset_s + duration_s) / dt))))
        y[start:stop] = amplitude

        label = f"Synthetic stimulus R{rnum if rnum is not None else '?'} ({params.get('label', rname)})"
        out.append(Series(
            name=label,
            data=y[:, None],
            sampling_interval=dt,
            units=params.get("units", "V"),
            metadata={
                "stimulus_preview": True,
                "synthetic_stimulus": True,
                "routine_number": rnum,
                "routine_name": rname,
                "stimulus_onset_s": onset_s,
                "stimulus_duration_s": duration_s,
                "stimulus_amplitude": amplitude,
                "source": "routine metadata fallback",
            },
        ))

    out.sort(key=lambda s: (s.metadata.get("routine_number") or 10**9, s.name))
    return out


def _infer_pulse_from_routine_metadata(routine_name: str, routine_text: str = "") -> dict[str, Any] | None:
    """Infer a simple pulse stimulus from SutterPatch routine metadata text."""
    haystack = f"{routine_name} {routine_text}".lower()
    if not any(token in haystack for token in ("flash", "stim", "led", "ttl", "trig", "pulse", "dac", "out")):
        return None

    duration_s = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*ms\s*(?:flash|pulse|stim)?", haystack)
    if m:
        duration_s = float(m.group(1)) / 1000.0
    if duration_s is None:
        m = re.search(r"(\d+(?:\.\d+)?)\s*s\s*(?:flash|pulse|stim)", haystack)
        if m:
            duration_s = float(m.group(1))
    if duration_s is None:
        duration_s = 0.05

    amplitude = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*v\b", haystack)
    if m:
        amplitude = float(m.group(1))
    if amplitude is None:
        amplitude = 1.0

    onset_s = None
    # Some routine blobs contain text fragments like "1-0.120" near output
    # channel labels. Treat the second number as a possible onset only if it
    # falls inside a normal sweep range.
    for m in re.finditer(r"(?:^|[^0-9.])(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)(?:[^0-9.]|$)", haystack):
        candidate = float(m.group(2))
        if 0 <= candidate <= 10:
            onset_s = candidate
            break

    label = routine_name
    if "led" in haystack:
        label = "LED pulse"
    elif "flash" in haystack:
        label = "Flash pulse"
    elif "ttl" in haystack or "trig" in haystack:
        label = "TTL/trigger pulse"

    return {
        "duration_s": duration_s,
        "amplitude": amplitude,
        "onset_s": onset_s,
        "units": "V",
        "label": f"{label}, {duration_s*1000:g} ms, {amplitude:g} V",
    }


def _parse_sutter_note_fields(note: str) -> dict[str, str]:
    """Parse SutterPatch note fields encoded as Key^>Value%% chunks."""
    fields: dict[str, str] = {}
    if not note:
        return fields
    for part in str(note).replace("\r", "").split("%%"):
        if "^>" not in part:
            continue
        key, value = part.split("^>", 1)
        key = key.split("|")[-1].strip()
        value = value.strip()
        if key:
            fields[key] = value
    return fields

def _load_generic_pxp_waves(path: Path, filesystem: dict[str, Any], parse_report: dict[str, Any]) -> Recording:
    waves: list[tuple[str, Any]] = []
    _collect_igor_waves(filesystem, waves)

    series: list[Series] = []
    sweeps: list[Sweep] = []
    for name, wave_obj in waves:
        arr = _wave_to_array(wave_obj)
        if arr is None or not np.issubdtype(arr.dtype, np.number):
            continue
        arr = np.asarray(arr, dtype=float)
        if arr.ndim == 1:
            arr = arr[:, None]
        elif arr.ndim != 2:
            continue
        sampling_interval = _sampling_interval_seconds(_wave_header(wave_obj))
        s = Series(name=name, data=arr, sampling_interval=sampling_interval, metadata={"igor_name": name})
        series.append(s)
        sweeps.extend(s.sweep(i) for i in range(s.sweep_count))

    if not series:
        raise LoaderError("PXP was readable, but no numeric waves were found.")

    return Recording(path=path, source_format="pxp", sweeps=sweeps, series=series, metadata={"parse_report": parse_report})


def _collect_igor_waves(obj: Any, out: list[tuple[str, Any]], prefix: str = "") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            name = f"{prefix}/{_decode_key(key)}" if prefix else _decode_key(key)
            if _wave_to_array(value) is not None:
                out.append((name, value))
            else:
                _collect_igor_waves(value, out, name)
    elif isinstance(obj, (list, tuple)):
        for i, value in enumerate(obj):
            _collect_igor_waves(value, out, f"{prefix}/{i}")


def _wave_dict(obj: Any) -> dict[str, Any] | None:
    if hasattr(obj, "wave"):
        obj = obj.wave
    if not isinstance(obj, dict):
        return None
    if "wave" in obj and isinstance(obj["wave"], dict):
        return obj["wave"]
    if b"wave" in obj and isinstance(obj[b"wave"], dict):
        return obj[b"wave"]
    return obj


def _wave_to_array(obj: Any) -> np.ndarray | None:
    d = _wave_dict(obj)
    if d is None:
        return None
    for key in ("wData", b"wData", "data", b"data"):
        if key in d:
            try:
                arr = np.asarray(d[key])
            except Exception:
                continue
            if arr.size:
                return arr
    return None


def _wave_header(obj: Any) -> dict[str, Any]:
    d = _wave_dict(obj)
    if not isinstance(d, dict):
        return {}
    return d.get("wave_header") or d.get(b"wave_header") or {}


def _wave_note(obj: Any) -> str:
    d = _wave_dict(obj)
    note = b""
    if isinstance(d, dict):
        note = d.get("note") or d.get(b"note") or b""
    if isinstance(note, bytes):
        return note.decode("utf-8", "replace")
    return str(note)


def _wave_to_text_table(obj: Any) -> list[list[str]]:
    arr = _wave_to_array(obj)
    if arr is None:
        return []
    out: list[list[str]] = []
    for row in np.asarray(arr):
        out.append([x.decode("utf-8", "replace") if isinstance(x, bytes) else str(x) for x in row])
    return out


def _sampling_interval_seconds(wave_header: dict[str, Any]) -> float | None:
    sf_a = wave_header.get("sfA")
    try:
        value = float(np.asarray(sf_a).ravel()[0])
    except Exception:
        return None
    return value if value > 0 else None


def _decode_units(raw: Any) -> str:
    try:
        arr = np.asarray(raw).ravel()
        if arr.dtype.kind in {"S", "U"}:
            return b"".join(x if isinstance(x, bytes) else str(x).encode() for x in arr).decode("utf-8", "replace").strip()
    except Exception:
        pass
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace").strip()
    return str(raw).strip() if raw is not None else ""


def _decode_key(key: Any) -> str:
    if isinstance(key, bytes):
        return key.decode("utf-8", "replace")
    return str(key)


def _parse_sutter_series_name(name: str) -> dict[str, Any]:
    m = re.match(r"R(?P<routine>\d+)_S(?P<signal>\d+)_(?P<routine_name>.+)$", name)
    if not m:
        return {}
    return {
        "routine_number": int(m.group("routine")),
        "signal_number": int(m.group("signal")),
        "routine_name": m.group("routine_name"),
    }
