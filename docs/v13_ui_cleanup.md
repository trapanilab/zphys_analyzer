# v13 UI cleanup

## Noise rejection

The noise-rejection field has been relabeled:

```text
Advanced optional: ignore tiny threshold wiggles (0 = auto)
```

It is not normally something that must be set. Leave it at `0` unless small
near-threshold fluctuations are being counted as events.

## Stimulus windows

The window group is now titled:

```text
Stimulus detection windows / cursor pairs
```

It includes a note explaining 20 Hz / 50 ms detection windows, plus a button:

```text
Set 20 Hz / 50 ms Defaults
```

Then set onset and number of windows and click:

```text
Generate Stimulus Windows
```

## Trackpad/mouse wheel behavior

Numeric spin boxes now ignore mouse-wheel/trackpad scrolling. This prevents
accidentally changing values when scrolling the side panel.
