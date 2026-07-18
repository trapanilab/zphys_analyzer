# v8 displayed-trace analysis changes

## Main bug fixed

Before v8, event detection could redraw the original raw sweep before detecting events. That meant:

1. baseline-subtract current sweep
2. click Find Spikes / Events
3. graph jumps back to original offset

v8 fixes this by storing the plotted/processed data in:

```python
self._displayed_traces
```

Event detection can now run on the displayed trace instead of reloading the raw sweep.

## Analysis scope

The Analysis tab now has:

- `Analyze displayed trace(s)`
- `Analyze all sweeps in selected series`

Displayed trace scope means:
- current raw sweep
- baseline-subtracted sweep
- overlayed sweeps
- baseline-subtracted overlay
- concatenated trace

All-series scope means:
- use every sweep in the selected SutterPatch series
- independent of what is currently displayed

## Baseline subtraction

The `Baseline Subtract` button respects the selected scope.

If `Analyze displayed trace(s)` is selected:
- baseline subtracts the currently displayed trace(s)

If `Analyze all sweeps in selected series` is selected:
- baseline subtracts every sweep in the selected series
- displays an overlay of the baseline-subtracted traces

## Concatenated detection

Concatenated traces are now stored as one displayed trace with a real timebase.
Event detection works on that concatenated displayed trace when `Analyze displayed trace(s)` is selected.

## Result storage

Detected events are still stored as:

```python
self._last_detection_rows
self._last_detection_arrays
```

Displayed/processed traces are stored as:

```python
self._displayed_traces
```
