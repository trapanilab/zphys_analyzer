# v81 Field Potential analysis

Adds a Field Potential main tab that ports the automatic analysis from
BT_FieldPotentialBatch_v2_15.ipf.

Implemented:
- Field-potential settings:
  - stimulus onset
  - stimulus length
  - search offset
  - RMS window
  - RMS tolerance
  - baseline subtraction using the final RMS-window mean
- Analyze current sweep
- Analyze selected sweeps
- FP result table
- FP CSV export
- Plot review for selected FP row
- Plot markers for:
  - extrapolated onset
  - peak
  - trough
  - RMS return

Measurements:
- stim_to_peak_s
- fp_latency_s
- fp_amplitude
- fp_length_s
- onset_time_s / onset_y
- peak_time_s / peak_y
- trough_time_s / trough_y
- return_time_s
- status

Notes:
- This is the automatic/batch portion of the Igor program.
- Editable manual review can be added after testing the automatic output and UI flow.
