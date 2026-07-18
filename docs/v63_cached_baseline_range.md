# v63 cached baseline range

Baseline overlays now cache the display range while the baseline-subtracted
matrix is already available. The Autoscale button reuses that cached range
instead of rescanning displayed trace objects.

This should fix:
- baseline-subtracted traces moving out of view after offset removal
- Autoscale freezing the UI after baseline overlays
