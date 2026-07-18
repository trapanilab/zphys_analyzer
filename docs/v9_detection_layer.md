# v9 detection layer changes

## Re-clicking Find Spikes / Events

Before v9, every click added another set of marker symbols to the plot. v9 stores
marker plot items in:

```python
self._detection_marker_items
```

Each new detection run removes the old marker items first, clears the results
table, and overwrites:

```python
self._last_detection_rows
self._last_detection_arrays
```

## Random threshold-line detections

The detector now requires detected events to move a meaningful distance beyond
the threshold. The Analysis tab includes:

```text
Min amplitude beyond threshold (0 = auto)
```

- `0` uses an adaptive value: 5% of the robust 1st-to-99th percentile trace range.
- A positive value uses that exact y-unit distance beyond the threshold.

For downward detection, the trough must be at least this far below the threshold.
For upward detection, the peak must be at least this far above the threshold.

This avoids small noise fluctuations or near-threshold chatter being counted as
events.
