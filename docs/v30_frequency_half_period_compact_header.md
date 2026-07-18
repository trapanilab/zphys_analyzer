# v30 frequency half-period and compact data header

## Frequency behavior

Manual `Frequency (Hz)` entry now updates:

- the period readout
- the first window width, set to half the period

For example:

```text
20 Hz -> period 50 ms -> window width 25 ms
```

The paired-window offset/gap now defaults to 100 ms.

## Compact top panel

The top data controls were consolidated into a compact `Data / sweep` grid:

- Load File
- file/status label
- Signal selector
- Series selector
- Sweep number
- previous/next sweep buttons

This saves vertical room while preserving the same controls.
