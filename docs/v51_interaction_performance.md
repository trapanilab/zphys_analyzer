# v51 interaction performance

This version targets beachballing when many traces are overlaid and the
threshold line is dragged.

Changes:

- Removed the live text label from the movable threshold line.
- Removed the duplicate `sigPositionChanged` threshold callback.
- Throttled threshold drag UI updates to about every 35 ms.
- Overlay and baseline-overlay displays now render many traces as one combined
  PlotDataItem with NaN separators instead of adding one graphics item per sweep.
- Overlay display is capped to the first 50 sweeps for plotting responsiveness;
  full-resolution trace data remain stored for analysis.
- Display-only decimation is stronger for overlays; analysis arrays remain
  full-resolution.
