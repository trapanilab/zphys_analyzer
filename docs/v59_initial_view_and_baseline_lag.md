# v59 initial view and baseline lag

Fixes:
- New single traces now apply an explicit display range immediately after plotting,
  so first-loaded traces should be visible without pressing Autoscale.
- Removed the expensive post-baseline explicit range scan over all baseline traces.
  Baseline now preserves the existing X/time view and disables live autoRange
  without recomputing full displayed bounds.
- Removed duplicate autoscale calls after series/signal changes because
  `update_plot()` now applies the initial range.
- Threshold readout/edit formatting now uses compact notation, with two digits
  after the decimal in scientific notation.
