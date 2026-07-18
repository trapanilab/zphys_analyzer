# v26 adaptive numeric display

The GUI now uses adaptive significant-figure formatting instead of fixed decimal places.

This prevents small electrophysiology-scale values from being displayed as `0.000`.

Rules:

- threshold/amplitude/general values: 4 significant figures
- values smaller than 1e-3 or larger than/equal to 1e4 use scientific notation
- times use compact second formatting, with scientific notation below 1e-4 s

Underlying detection rows and arrays still store full-precision floats.
