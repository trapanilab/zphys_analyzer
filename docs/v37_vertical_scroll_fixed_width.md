# v37 vertical scrolling with fixed-width controls

The tab-local vertical scrolling from v35/v36 is retained, but horizontal
scrolling is disabled.

Changes:

- Left control panel has a fixed/narrow width again.
- Tab scroll areas are vertical-only.
- Tab content is constrained to the viewport width so controls wrap rather than
  expanding sideways.
- Series selector is still wider than before, but no longer forces a horizontal
  scrollbar.
- File Tools output wraps to widget width.
- File Tools buttons are shortened to `Metadata` and `Data Location` with
  tooltips preserved.
