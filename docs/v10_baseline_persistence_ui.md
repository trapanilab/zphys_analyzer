# v10 baseline persistence and UI changes

## Persistent baseline subtraction

v10 adds persistent baseline state:

```python
self._baseline_enabled_by_trace_key
```

Keys are `(series_name, sweep_index)`. When `Keep baseline subtraction when changing sweeps`
is checked, returning to a marked sweep redraws it baseline-subtracted.

Use `Clear Persistent Baseline` to reset this state.

## Analysis Tools after load

After a file loads, the GUI automatically switches to the `Analysis Tools` tab.

## Side panel text clipping

The left control panel is now inside a scroll area and is wider. Long labels use word wrapping.

## Noise reject / min distance past threshold

This field is optional and can usually stay at `0 = auto`.

It prevents small noise fluctuations sitting on the threshold line from being counted as events.
A positive value is in the same units as the displayed trace. For downward events, the trough
must go this far below the threshold. For upward events, the peak must go this far above it.
