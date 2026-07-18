# v27 two-decimal adaptive display

Numeric GUI formatting now uses two decimals while still avoiding loss of small
scientific-notation values.

Rules:

- ordinary amplitudes/thresholds: two fixed decimals, e.g. `12.35`
- very small values below `0.01`: scientific notation with two mantissa decimals,
  e.g. `2.34e-10`
- very large values above/equal to `10000`: scientific notation with two mantissa
  decimals
- time values keep compact second formatting suitable for millisecond windows

Underlying detection rows and arrays still store full-precision floats.
