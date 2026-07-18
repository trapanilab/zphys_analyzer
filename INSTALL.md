# zPhys Python installation guide

This package installs the zPhys Python GUI for electrophysiology analysis, including:

- SutterPatch / Igor PXP loading
- ABF / IBW / CSV loading
- sweep display, overlay, baseline subtraction, averaging, FFT, concatenation
- spike/event detection with detection windows, ISI export, first-in-window markers
- SutterPatch conservative stimulus/output handling
- larval zebrafish field-potential analysis with FP latency/amplitude/length results

The app is cross-platform and should run on macOS and Windows when Python 3.10 or newer is available. Python 3.11 is recommended.

---

## Quick install: Mac

1. Unzip the package.
2. Open the `scripts` folder.
3. Double-click:

```text
install_mac.command
```

4. If macOS asks whether to allow the script to run, choose allow/open.
5. When installation finishes, start the app by double-clicking:

```text
run_mac.command
```

The installer creates a local `.venv` folder inside the zPhys folder. This keeps zPhys dependencies separate from other Python projects.

---

## Quick install: Windows

1. Unzip the package.
2. Open the `scripts` folder.
3. Double-click:

```text
install_windows.bat
```

4. When installation finishes, start the app by double-clicking:

```text
run_windows.bat
```

The installer creates a local `.venv` folder inside the zPhys folder. This keeps zPhys dependencies separate from other Python projects.

---

## If Python is not installed

### Mac

Install Python 3.11 or newer from:

```text
https://www.python.org/downloads/macos/
```

After installing Python, run:

```text
scripts/install_mac.command
```

### Windows

Install Python 3.11 or newer from:

```text
https://www.python.org/downloads/windows/
```

Important: during the Windows Python installer, check:

```text
Add python.exe to PATH
```

After installing Python, run:

```text
scripts/install_windows.bat
```

---

## Conda / Miniforge option

This is a good option for lab computers or users who already use conda.

### Mac or Windows

Install Miniforge from:

```text
https://conda-forge.org/download/
```

Then use one of these:

Mac:

```text
scripts/install_conda_mac.command
```

Windows, from a Miniforge Prompt:

```text
scripts\install_conda_windows.bat
```

To run after conda install:

```bash
conda activate zphys
zphys
```

---

## Manual install from Terminal / Command Prompt

From inside the unzipped zPhys folder:

```bash
python -m venv .venv
```

Mac/Linux:

```bash
source .venv/bin/activate
```

Windows:

```bat
.venv\Scripts\activate
```

Then:

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
python -m zphys.app
```

---

## How to update zPhys

1. Download/unzip the newer zPhys package.
2. Run the install script again in the new folder.
3. Use the new run script.

Each package keeps its own `.venv`, so old and new versions can coexist.

---

## Troubleshooting

### `python` or `python3` not found

Install Python 3.11 or newer. On Windows, make sure `Add python.exe to PATH` was checked.

### `conda command not found`

Conda is only needed if you choose the conda install path. Install Miniforge, reopen Terminal/Prompt, then try again.

### macOS says the `.command` file cannot be opened

Right-click the file and choose **Open**, or open Terminal and run:

```bash
chmod +x scripts/install_mac.command scripts/run_mac.command
```

Then double-click again.

### PySide6 install is slow

PySide6 is the Qt GUI toolkit and can take a few minutes to download/install. This is normal.

### App starts but no graph appears

Load a supported data file first:

- `.pxp`
- `.ibw`
- `.abf`
- `.csv`

---

## Main launch commands

After installation:

Mac:

```text
scripts/run_mac.command
```

Windows:

```text
scripts\run_windows.bat
```

From activated environment:

```bash
zphys
```

or

```bash
python -m zphys.app
```
