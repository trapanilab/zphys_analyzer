# v7 detection/results changes

## Threshold control

The old numeric spinbox with up/down arrows has been replaced by:

- a live readout: `Threshold: ...`
- a manual entry field: type a number and press Return
- the draggable threshold line
- the threshold slider

The previous spinbox was meant for exact threshold entry, but it was confusing
because the line/readout updated while the spinbox could remain visually stale.

## Negative-going detection

The threshold detector now explicitly supports downward crossings:

```text
trace crosses from >= threshold to < threshold
```

For negative events, the reported event amplitude is the local minimum after the
crossing, not merely the crossing sample. This better matches the usual workflow
where the line is placed on the negative side of the event and the actual trough
amplitude is the detected amplitude.

## Results panel instead of popup

The modal detection popup has been removed. Detection results are now written to
the bottom results panel.

The table columns are:

- series
- sweep
- event
- time_s
- amplitude
- crossing_time_s
- direction

## Stored arrays

Detected results are stored on the main window as:

```python
self._last_detection_rows
self._last_detection_arrays
```

`self._last_detection_rows` is a list of dictionaries with full event metadata.

`self._last_detection_arrays` contains NumPy arrays:

```python
{
    "time_s": np.ndarray,
    "amplitude": np.ndarray,
    "sweep": np.ndarray,
    "event": np.ndarray,
}
```

These arrays are the starting point for downstream analyses such as spike count,
latency, ISI, vector strength, adaptation, intensity functions, and amplitude
summaries.

## Export

The results panel has an `Export CSV` button for saving detected event times and
amplitudes.
