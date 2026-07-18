# v64 visible-baseline-only display path

The Baseline button now baseline-subtracts only the currently visible/plotted
traces for display. This avoids the previous fallback path that could create,
store, plot, and autoscale a huge list of full-resolution baseline traces.

Fixes:
- baseline-subtracted traces are immediately ranged using the new baseline data
- offset-removal should no longer move traces out of view
- Autoscale is capped to visible traces and should not freeze the UI
