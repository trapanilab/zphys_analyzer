# v16 window UI wording and workflow

## Add One Manual Window vs Generate Stimulus Windows

- `Add One Manual Window` creates one draggable cursor-pair region on the plot.
  Use this for one custom detection epoch.

- `Generate Stimulus Windows` creates a repeated set of windows based on:
  - onset after sweep start
  - stimulus frequency
  - window width
  - number of windows

For 20 Hz stimulation, the period is 50 ms.

## Defaults

The stimulus onset default is now 100 ms.

## Paired window wording

The paired option is now:

```text
Generate paired second window
```

The second window width defaults to the first window width when paired windows
are enabled.

## Run detection from Windows tab

The Windows tab now has:

```text
Find Spikes / Events in Windows
```

This lets the user fine tune windows and run detection without returning to the
Detect tab.
