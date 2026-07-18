# v39 Analysis Tools width fix

The Analysis Tools tab was still using some wide grid/button rows after
horizontal scrolling was disabled. This caused right-side controls to be cut off.

Changes:

- Analysis setup now uses compact stacked controls instead of a wide grid.
- Window shortcut button rows are vertical/stacked.
- Long button and label text in Analysis Tools was shortened.
- Spinboxes in Analysis Tools have maximum widths.
- The event results table is capped so it does not force the tab wider.
- Vertical-only tab scrolling is retained.
