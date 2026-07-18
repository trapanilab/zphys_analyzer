# v58 autoRange state fix

v57 restored fast plotting and made baseline vectorized, but Baseline still made
the plot sluggish afterwards. The likely cause was `plot.autoRange()` leaving
pyqtgraph live auto-range enabled over many baseline overlay curves. That causes
pyqtgraph to recompute bounds during later zoom/pan/threshold interactions.

v58 changes:
- Autoscale is a no-op when no traces are displayed.
- Autoscale uses explicit sampled X/Y ranges and then disables live autoRange.
- Baseline overlay uses explicit ranges and does not call `plot.autoRange()`.
- Direct plotting paths disable live autoRange before clearing/redrawing.
- Quiet voltage traces still get a minimum display span without leaving autoRange enabled.
