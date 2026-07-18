# v68 fast concatenate display

Concatenate Selected Sweeps now treats concatenation as a display operation:

- The full concatenated vector is created only long enough to produce a display-sized copy.
- The plot uses a decimated display trace for long concatenations.
- Autoscale uses the displayed/cached range rather than scanning a huge full-resolution concatenated vector.
- Threshold slider range updates are not run over the huge concatenated vector during display.
