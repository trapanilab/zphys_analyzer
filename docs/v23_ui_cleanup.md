# v23 UI cleanup

## Baseline controls

`Keep baseline subtraction when changing sweeps` has moved into the Common
actions baseline area, next to Baseline Subtract and the all-selected-sweeps
baseline option.

## Selected sweeps label

The all-series analysis radio button is shortened to:

```text
Selected sweeps
```

A tooltip explains that it means selected sweeps from the current series.

## Load button

The redundant File Tools `Load File` button was removed. The main top `Load File`
button remains. The previous `Load Data`/`Load File` controls did the same thing.

## Overlay sweeps

Added/restore obvious overlay controls:

- Common actions: `Overlay Sweeps`
- Display Tools: `Overlay All Sweeps`

These call the existing overlay-all-sweeps display path and respect selected
sweeps where the series-trace selection pipeline is active.
