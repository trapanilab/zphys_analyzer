# Igor IPF analysis/display mapping notes

This document records the first pass at checking the Python analysis behavior against the uploaded Igor Pro procedures.

## Where the data is stored in the Python port

The loaded file is stored in the main window state:

```python
window.state.recording
```

That object is a `Recording` from `zphys/models.py`.

For SutterPatch `.pxp` files:

```python
recording.series
```

is a list of `Series` objects. Each `Series` corresponds to one Igor/SutterPatch data wave:

```text
root:SutterPatch:Data:R#_S#_RoutineName
```

For example:

```text
root:SutterPatch:Data:R1_S1_Action_Fjet20Hz
```

becomes a Python `Series` whose data are stored here:

```python
recording.series[n].data
```

The array layout is:

```text
rows = time points
columns = sweeps/episodes
```

A single sweep is created from one column:

```python
sweep = recording.series[n].sweep(i)
sweep.y          # NumPy 1D trace
sweep.timebase() # seconds, when sampling interval exists
```

## Igor Find_Peaks behavior checked

The uploaded `JT_zphys_event_analysis_rtGlobals3_full_v5.ipf` function `Find_Peaks()` uses Igor `FindLevel` / `FindLevels`, not a generic peak maximum finder.

Important Igor elements:

- `eventamp = root:A:eventamp` is the detection threshold.
- `spiketime = root:A:spiketime` is used to set `spikewidth`.
- `FindLevels /B=(boxNum)` applies box smoothing.
- `FindLevels /M=(spikewidth)` enforces event separation/width.
- The function can run over one sweep or multiple sweeps depending on the Multiple checkbox.
- Event amplitude is then estimated in a window after each crossing using `wavemax` and `wavemin`.

The v4 Python detector was changed from simple `find_peaks()` to an Igor-like threshold-crossing detector:

```python
detect_spikes(..., threshold=..., polarity="above" or "below", boxcar_points=..., min_distance_points=...)
```

The GUI now exposes:

- threshold line/spinbox/slider
- direction: above or below threshold
- min spacing/width in ms
- smoothing box points

## Overlay behavior

If the display mode is `Overlay All Sweeps in Series`, `Find Spikes / Events` now analyzes every displayed sweep in that series, not only the selected sweep. The marker overlay and histogram are generated from the combined per-sweep detection results.

## Still not fully ported

The Python code does not yet fully recreate all Igor side effects such as creating every `root:A:Avg:*` output wave, accumulated notebook reporting, cursor-pair restricted detection, or all graph-panel controls. Those should be ported feature-by-feature after comparing outputs against Igor.
