# v66 fast single-trace display path

The single-sweep/current-sweep path now mirrors the fast overlay path:
direct `plot.plot(x, y)`, no explicit sampled range scan, and no threshold-slider
range update during drawing.

A one-shot native pyqtgraph autoRange is used after the direct plot so the trace
is visible, then live autoRange is disabled.
