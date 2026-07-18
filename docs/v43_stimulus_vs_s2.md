# v43 stimulus waveform vs S2 recorded signal

## S2 is now treated as recorded data

S2 waves are treated as simultaneously recorded input signals, not as stimulus
waveforms. The loader no longer populates `Recording.stimulus` from S2 waves.

The Display Tools tab now has a separate `Display Matching S2` button. It finds
an S2 series matching the current routine number/name and displays the matching
sweep. If the selected series is already S2, it displays that selected S2 sweep.

The Signal selector refresh path was also fixed so choosing S1, S2, or All updates
the series list and immediately redraws the selected trace.

## Actual stimulus/output previews

The PXP loader now searches the broader SutterPatch file for output/stimulus
preview waves, especially under `AppControl/Routines/WavePreview`. Candidate
waves include notes/names such as:

- `StimOUT`
- `DigOUT`
- `AuxOUT`
- `TTL`
- `DAC`

These stimulus preview waves are stored in:

```python
recording.metadata["stimulus_series"]
```

and exposed as `recording.stimulus` sweeps.

## Display Tools controls

- `Display Matching S2`: displays recorded S2 input data.
- `Display Stimulus Waveform`: displays an output/stimulus preview waveform from
  the PXP file.
- `Overlay Stimulus on Current`: overlays the stimulus preview in orange on the
  currently selected S1 or S2 sweep.

Stimulus overlays are intentionally separate from S2 display.
