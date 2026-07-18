# v67 baseline X-range idempotence

Repeated Baseline presses were changing the X axis because the current X range
was preserved and then padded again each time. v67 preserves the current X range
exactly when Baseline supplies a `preserve_x` range.

Also, pressing Baseline again on already baseline-subtracted traces is treated as
a display refresh rather than another baseline operation.
