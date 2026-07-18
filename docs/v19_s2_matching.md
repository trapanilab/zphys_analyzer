# v19 S2 matching and detection button placement

## Find button placement

`Find Spikes / Events` has been moved to the top of the Threshold Detection panel.

## S2/stimulus matching

`Display Matching Stimulus / S2` now uses a more robust matching order:

1. same routine number and signal number 2
2. same routine name and signal number 2
3. direct name substitution from `_S1_` to `_S2_`
4. nearest following S2 series as a fallback

The results panel reports which S2 series was displayed.
