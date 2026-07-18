# v65 fast automatic display path

Automatic load/series/signal switching now uses the same lightweight display
path as the Display Current Sweep button.

Changes:
- Draw the sweep first, then defer auto-thresholding to the Qt event loop.
- Use sampled statistics for auto-threshold and threshold-slider range.
- Block sweep-spin signals during programmatic series changes to avoid duplicate redraws.
- Remove the extra autoscale request from signal switching.
