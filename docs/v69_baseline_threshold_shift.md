# v69 baseline threshold shift

When Baseline shifts the visible trace by subtracting its mean, the threshold
line is now shifted by the same offset for the first visible trace before the
line is re-added to the plot.

This keeps the threshold line in the same relative position after baseline
subtraction instead of leaving it at the old raw-data value.
