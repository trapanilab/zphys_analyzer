# v12 sweep selection and stimulus window generator

## Where to select sweeps

The Analysis tab has a field labeled:

```text
Selected sweeps for all-series detection and concatenation
```

Use Igor-style one-based sweep numbers:

```text
1-5,8,10-12
```

Blank means all sweeps for all-series detection and concatenation.

## Concatenation

`Concatenate Selected Sweeps` uses the sweep selection field. For example:

```text
1-10
```

concatenates only sweeps 1 through 10 from the currently selected series.

## Detection windows

The `Detection windows / cursor pairs` section supports:

- Add Window: adds one draggable region
- Clear Windows: removes all regions
- Generate Stimulus Windows: creates repeated windows based on onset, frequency, width, and count

For 20 Hz stimulation:

```text
frequency = 20 Hz
period = 50 ms
```

If the goal is one detection window per stimulus cycle, set:

```text
Window width = 50 ms
```

Set `Onset after sweep start` to the stimulus onset latency in the sweep. For example, if stimulus starts
100 ms after the sweep begins:

```text
Onset after sweep start = 100 ms
Frequency = 20 Hz
Window width = 50 ms
Number of windows = number of stimulus cycles
```

Each generated window remains draggable for fine tuning.
