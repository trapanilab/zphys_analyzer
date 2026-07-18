# v53 Fjet stimulus selection

`SAS110716.pxp` contains a flat zero `StimOUT` WavePreview plus digital
`DigOUTWord`/`DigOUT1` previews. The previous stimulus selector penalized the
flat analog preview and therefore displayed the digital square word.

For Fjet routines such as `Action_Fjet20Hz`, this version creates a normalized
synthetic sine preview when the stored analog output preview is flat/missing.
The selector now prefers the reconstructed Fjet sine over digital output words.

The reconstructed sine is marked with `synthetic_kind="fjet_sine"` and uses a
separate right Y axis when overlaid, so the exact amplitude is less important
than the waveform shape and timing.
