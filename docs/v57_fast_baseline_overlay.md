# v57 fast baseline overlay

v56 restored fast plotting, but the Baseline button was still slow after overlay.
The remaining bottleneck was the all-selected-sweeps baseline branch:

- it rebuilt selected traces twice
- it baseline-subtracted sweep-by-sweep through helper calls
- it used a custom Y autoscale path that masked and concatenated displayed arrays

v57 adds a vectorized baseline path for the current series:

- selected sweep columns are baseline-subtracted in one NumPy operation
- displayed traces are created from the vectorized result
- plotting uses the restored direct `plot.plot(x, y)` loop
- autoscaling uses native pyqtgraph `autoRange` followed by restoration of the
  original X/time range
