# v54 stimulus source selection and safer automatic behavior

v53 reconstructed Fjet sine stimuli from routine names such as `Action_Fjet20Hz`.
That is not reliable for arbitrary experiments because SutterPatch stores the
true stimulus paradigm in routine/waveform parameter tables and routine copies,
not necessarily in the routine name.

This version keeps synthetic/name-derived candidates available for manual
inspection, but does not automatically treat them as trusted sources. If an Fjet
routine only has flat analog preview data and digital outputs, `Display Stimulus
Waveform` reports that automatic selection is ambiguous and asks the user to use
`Choose Stimulus Source`.

The chooser lists all stimulus candidates with provenance/tags, including stored
WavePreview waves, flat analog waves, digital outputs, and synthetic fallbacks.
