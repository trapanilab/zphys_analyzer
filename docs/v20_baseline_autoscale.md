# v20 baseline controls and autoscale

## Baseline button restored

The Baseline group is present in the Actions tab:

- Apply to all selected sweeps in all-series scope
- Baseline Subtract
- Clear Persistent Baseline

## Autoscale

Added `Autoscale Displayed Traces`.

It uses `self._displayed_traces` so it rescales to whatever is currently shown:

- current sweep
- overlay
- baseline-subtracted traces
- average
- concatenated trace
- matching S2/stimulus trace

The button is available in Display Tools and Actions.
