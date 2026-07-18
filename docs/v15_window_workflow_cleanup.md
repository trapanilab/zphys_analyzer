# v15 window workflow cleanup

## Paired window defaults

When `Generate two windows per cycle` is checked, the second window width now
defaults to the first window width. If the first window width is changed while
paired windows are enabled, the second window width follows it.

## Window controls in Detect and Windows

The Detect tab now includes compact window controls:

- Detect only inside these windows
- Add Window
- Generate Windows
- Clear

The full generator remains in the Windows tab.

## Advanced detection settings

Less commonly changed settings are now hidden in a collapsed panel:

```text
Advanced detection settings
```

This panel contains:

- min spacing / width
- smoothing box points
- ignore tiny threshold wiggles
- spacing conversion readout
