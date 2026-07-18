# v47 autoscale and stimulus overlay fix

- Autoscale now computes explicit X/Y ranges from displayed traces instead of
  relying on pyqtgraph `autoRange()`.
- Switching back from S2 to S1 should now show the full sweep immediately.
- `Overlay Stimulus on Current` was renamed to `Overlay Stimulus on Sweep`.
- Stimulus overlay now explicitly rebuilds the selected recorded sweep and plots
  it on the left Y axis, then overlays stimulus on the right Y axis.
