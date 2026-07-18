# v46 autoscale signal/series/stimulus displays

## Autoscale

The app now explicitly autoscale-ranges the plot after:

- switching the Signal selector between S1/S2/Sn/All
- selecting a new series
- displaying the matching S2 trace
- displaying the stimulus waveform
- overlaying the stimulus waveform

Autoscale is requested immediately and once again on the next Qt event-loop tick
so it runs after newly drawn curves and axes have settled.

## Signal selector

The Signal selector is populated from the loaded file's signal metadata. If a
file contains S3, S4, etc., those entries are listed when the loader can detect
the signal numbers from metadata or series names.
