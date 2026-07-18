# v55 responsiveness regression fix

This version fixes the responsiveness regressions introduced while addressing
S1/S2 and stimulus autoscale behavior.

Main fixes:

- Disconnect the stimulus right-axis `sigResized` callback when clearing the
  right-axis stimulus overlay.
- Unlink and remove the right-axis stimulus ViewBox more completely.
- Clear right-axis stimulus state before direct plotting paths such as overlay.
- Restore ordinary per-sweep overlay plotting instead of the one-large-path
  NaN-separated combined overlay workaround.
- Restore visible overlay line width.
- Reduce full autoscale scheduling from three range scans to immediate plus one
  event-loop pass.

The suspected root cause for progressive lag/freezing was stale right-axis
resize callbacks holding removed stimulus ViewBoxes alive after repeated
stimulus overlay/display transitions.
