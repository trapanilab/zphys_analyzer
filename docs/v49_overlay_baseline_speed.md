# v49 overlay/baseline redraw speed

Baseline subtraction after overlaying many sweeps was slow because the GUI was
redrawing up to 100 full-resolution curves and autoscale was scanning all full
arrays.

This version keeps all analysis data full-resolution, but uses display-only
decimation and pyqtgraph fast options for plotted curves:

- display traces are decimated to about 12k points per curve for plotting only
- pyqtgraph `autoDownsample`, `clipToView`, and peak downsampling are enabled
  where supported
- batch overlay redraws temporarily disable plot updates while curves are added
- autoscale range calculations sample very long arrays for speed

The underlying trace arrays used for baseline/event analysis are unchanged.
