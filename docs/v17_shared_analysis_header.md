# v17 shared analysis header

The Analysis Tools panel now has a persistent shared header above the subtabs.
This header remains visible while switching between Detect, Windows, and Actions.

Shared persistent controls:

- analysis scope
- selected sweeps
- detect only inside windows
- keep baseline subtraction
- baseline subtract all selected sweeps in all-series scope
- current detection-window summary

Subtabs now hold controls that are specific to a task:

- Detect: threshold and event detection
- Windows: stimulus/window generation and fine tuning
- Actions: baseline, average, FFT, concatenate

This avoids hiding global state inside one subtab while another subtab is active.
