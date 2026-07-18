# zPhys Python

Trapani Lab zPhys Python is a cross-platform GUI for electrophysiology analysis.

Current package version: **0.1.84**

## What it does

- Loads SutterPatch / Igor PXP files, IBW, ABF, and CSV.
- Displays sweeps and series.
- Provides baseline subtraction, overlay, average, FFT, and concatenation tools.
- Detects spikes/events with optional detection windows.
- Exports event timing, ISI, window-relative timing, and first-in-window event data.
- Handles SutterPatch stimulus/output information conservatively:
  - recorded/stored output signals are trusted
  - AppControl previews are marked preview-only
  - synthetic reconstruction from routine names is not used as source-of-truth
- Includes Field Potential analysis for larval zebrafish startle-response recordings:
  - stim-to-peak time
  - FP latency
  - FP amplitude
  - FP length
  - onset/peak/trough/return markers
  - CSV export

## Install

Start with:

```text
START_HERE.txt
```

Detailed instructions are in:

```text
INSTALL.md
```

Fast path:

Mac:

```text
scripts/install_mac.command
scripts/run_mac.command
```

Windows:

```text
scripts\install_windows.bat
scripts\run_windows.bat
```

## Developer / manual install

```bash
python -m pip install -e .
zphys
```

## Notes

This package is portable source code plus installer/launcher scripts. It is not yet a signed standalone `.app` or `.exe`. The included scripts make installation as close to plug-and-play as possible on machines with Python installed, and `INSTALL.md` explains how to install Python when it is missing.
