# v61 visible-trace autoscale

Autoscale now uses only the traces that are actually plotted on screen
(`_range_traces`) instead of scanning every full-resolution stored analysis trace.

This matters after baseline overlays: the app may store all baseline-subtracted
traces for analysis, but only the first plotted subset should be used for UI
range calculations. Baseline also now applies a quick range from the plotted
baseline traces immediately, so a second Autoscale press should not be needed.
