# SutterPatch PXP mapping notes

Inspected sample: `SAS110716.pxp`

## Key findings

- The file is an Igor packed experiment (`.pxp`) with SutterPatch folders.
- Normal `igor2.packed.load()` stops on one malformed wave record in this sample.
- A tolerant parser can skip that malformed record and still recover the main filesystem.
- Recovered location: `root:SutterPatch:Data`.
- Top-level data waves in that folder:
  - `ExperimentStructure`
  - routine/signal waves named like `R1_S1_Action_Fjet20Hz`
  - analysis waves under `root:SutterPatch:Data:Analysis`
  - metadata under `root:SutterPatch:Data:Meta`
  - routine definitions under `root:SutterPatch:Data:Routines`

## Data wave convention

Routine data waves follow:

```text
R{routine_number}_S{signal_number}_{routine_name}
```

Examples:

```text
R1_S1_Action_Fjet20Hz
R1_S2_Action_Fjet20Hz
R15_S1_Action_Light20Hz
R15_S2_Action_Light20Hz
```

The sample data waves are 2D numeric arrays:

```text
rows = time points
columns = sweeps / episodes
```

The Igor wave header `sfA[0]` was `0.0001`, so the initial Python loader treats the sampling interval as 0.0001 s, i.e. 10 kHz.

In this sample, `S1` appears to be the electrophysiology response channel and `S2` often appears to be the stimulus/command channel. The loader preserves both as selectable series and marks `S2` sweeps as stimulus sweeps.

## Example sample dimensions

- `R1_S1_Action_Fjet20Hz`: `(5002, 20)`
- `R1_S2_Action_Fjet20Hz`: `(5002, 20)`
- `R11_S1_New_Continous`: `(5000, 300)`
- `R20_S1_Action_Light20Hz`: `(5002, 297)`
- `R27_S1_Action_Light500msRecur`: `(36002, 16)`

## Loader implementation

The updated `load_pxp()` function:

1. tries normal `igor2.packed.load()`
2. falls back to tolerant parsing if a record fails
3. finds `root:SutterPatch:Data`
4. maps each `R#_S#_*` numeric 2D wave to a `Series`
5. exposes each column as a `Sweep`
6. preserves the parsed `ExperimentStructure` table in `recording.metadata`
