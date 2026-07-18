# v11 sweep selection and detection windows

## Concatenate selected sweeps

The old button label `Concatenate Selected Series` was misleading. The button is
now `Concatenate Selected Sweeps`.

Use the `Sweep selection` box in the Analysis tab to choose which sweeps to use:

```text
1-5,8,10-12
```

Blank means all sweeps for all-series operations and concatenation.

## Detection windows / cursor pairs

The Analysis tab now has a `Detection windows / cursor pairs` section.

- `Add Window` adds a draggable vertical region to the plot.
- `Clear Windows` removes all windows.
- `Detect only inside detection windows` restricts spike/event detection to those windows.

Each detection result row now includes:

- `window`
- `window_start_s`
- `window_end_s`

This is the first Python equivalent of the Igor cursor-pair workflow: spikes can
be assigned to different stimulus epochs, such as peaks of a sine-wave stimulus.

## Stored arrays

Detection arrays now include:

```python
self._last_detection_arrays["window"]
```

Rows include full per-event metadata in:

```python
self._last_detection_rows
```
