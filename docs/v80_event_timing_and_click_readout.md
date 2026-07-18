# v80 event timing and plot click readout

Detection result additions:
- `time_from_window_start_s`: event time relative to the active detection-window start.
- `crossing_time_from_window_start_s`: threshold-crossing time relative to the active detection-window start.
- `isi_s`: inter-spike interval within the same source/series/sweep/trace/window group.
- `event_in_window`: event ordinal within the current detection window.
- `first_in_window`: true for the first detected event in each detection window.

Display additions:
- First-in-window events are highlighted with a different marker symbol/color.
- Ordinary events remain blue circle markers.
- Clicking in the plot reports the clicked x/y coordinate and the nearest event or trace point in the results summary.

Export additions:
- CSV export includes the new ISI, window-relative timing, and first-in-window fields.
