# v3 usability changes

These changes address the first successful run against `SAS110716.pxp`.

## Signal filtering

The main window now has a `Signal` dropdown:

- `S1`
- `S2`
- any other signal numbers discovered in the file
- `All`

The default is `S1` when available.

## Series navigation

The `Series` dropdown is filtered by the selected signal. This makes the SutterPatch view much less cluttered.

## Threshold behavior

The threshold control now operates in the same y-units as the displayed trace.

The plot includes a movable horizontal threshold line. You can:

- drag the line on the plot
- type a value in the spinbox
- move the slider
- click `Center Threshold on Trace`

All three threshold controls stay synchronized.

## Enabled buttons

The following buttons now perform real actions:

### Analysis tab

- `Find Spikes / Events`
- `Average Selected Series`
- `Baseline-Subtract Current Sweep`
- `FFT Current Sweep`
- `Concatenate Selected Series`

### Display tab

- `Display Current Sweep`
- `Overlay All Sweeps in Series`
- `Display Average`
- `Display Matching Stimulus / S2`
- `Display Spike/Event Histogram`
- `Clear Plot`

These are first-pass implementations designed for interactive validation against Igor output.
