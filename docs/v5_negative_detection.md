# v5 negative/downward event detection

This update changes the event detector workflow to match the common zPhys use case where the threshold line is placed on the negative side of the events.

## Detection dropdown

The detector now has three modes:

- `Auto from threshold` — default. If the threshold is below the trace median/baseline, detect downward threshold crossings. If it is above the median/baseline, detect upward crossings.
- `Below threshold / downward` — always detect downward-going events.
- `Above threshold / upward` — always detect upward-going events.

## Auto threshold

`Center Threshold on Trace` now defaults to a negative-going threshold unless upward detection is explicitly selected.

## Practical use

For your usual downward event workflow:

1. Leave `Detect` set to `Auto from threshold`, or choose `Below threshold / downward`.
2. Drag the threshold line to the negative side of the events.
3. Click `Find Spikes / Events`.

If `Overlay All Sweeps in Series` is active, the detector runs across all displayed sweeps in the selected series.
