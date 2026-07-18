# v33 window/baseline/view cleanup

## Paired windows

The second-window width now always mirrors the first-window width. The second
width control is disabled and marked as automatic, so it cannot drift away from
the half-period window width.

## Baseline controls

Removed the duplicate Actions-panel checkbox that redefined
`self.baseline_all_checkbox`. The Actions panel now references the top Baseline
options instead:

- Keep baseline
- All selected

This avoids conflicting/redundant state.

## Plot view behavior

Autoscale now preserves the current X/time view and only rescales Y for the
visible data.

Baseline subtraction now preserves the current X/time view and rescales Y to the
baseline-subtracted data in that same time window.
