# v48 amplifier PXP support and friendlier autoscale

## New amplifier PXP behavior

`AP_260204_0.pxp` stores recorded SutterPatch data in `root:SutterPatch:Data`
with one sweep per routine and no saved `WavePreview` stimulus waves. The loader
now detects this and creates synthetic fallback stimulus pulse previews from the
routine metadata/routine names when possible, e.g. `50msflash_5V`.

These fallback stimuli are marked with `synthetic_stimulus=True` metadata so they
are distinguishable from true stored command-preview waves.

## Autoscale behavior

Y autoscale now enforces a minimum vertical span for quiet voltage traces, so
baseline-only traces are not zoomed until background noise fills the whole plot.
For voltage traces stored in volts near zero, the minimum displayed Y span is
about 1 mV.
