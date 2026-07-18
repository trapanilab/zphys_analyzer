# v25 compact numeric display

GUI numeric display is now rounded for readability:

- amplitudes and threshold values: 3 decimal places
- times and window boundaries: 4 decimal places in seconds

The underlying detection rows and arrays still store full-precision floats for
analysis/export. This only changes the visible table/readouts.
