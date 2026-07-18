# v79 conservative SutterPatch stimulus handling

SutterPatch support clarified that:
- AppControl folders are internal execution state and should not be used as dataset stimulus data.
- Data:Routines contains an encoded copy of routine settings, but output waveform regeneration currently requires SutterPatch.
- Existing files should be opened in SutterPatch to generate/store virtual output signals.
- Future acquisitions should record stimulus/output waveforms directly.

Changes:
- No longer synthesize Fjet sine or pulse stimulus candidates from routine names/Data:Routines.
- AppControl WavePreview candidates are marked preview-only / not authoritative.
- Automatic stimulus display only trusts non-flat, non-synthetic, non-preview stored/recorded output candidates.
- UI messages now explain how to handle old and future files.
