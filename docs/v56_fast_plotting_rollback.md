# v56 fast plotting rollback

v55 fixed a likely stimulus right-axis callback leak, but the app was still much
slower than earlier versions. v56 reverts the plotting/autoscale layer to the
earlier fast behavior while retaining the right-axis cleanup fix and newer loader
work.

Changes:
- Restored pyqtgraph native `autoRange` instead of explicit NumPy range scanning.
- Removed active display decimation from normal plotting paths.
- Restored direct `plot.plot(x, y)` calls for single traces, overlay, and baseline overlay.
- Restored immediate threshold line updates instead of throttled timer updates.
- Kept the stimulus right-axis callback disconnect/unlink cleanup from v55.
- Kept newer PXP loader and stimulus-source safety work.
