# v40 tab scroll width restore

The tab-local scroll change originally fixed vertical scrolling, but later
patches overconstrained the tab content width to prevent horizontal panning.
That made all three tabs narrower than necessary.

This version keeps the intended scroll behavior:

- the top header/common controls stay fixed
- only the active tab content scrolls vertically
- horizontal scroll bars remain off
- horizontal trackpad movement is ignored inside tab scroll areas

But it restores normal width behavior:

- tab content expands to the available left-panel width
- the left panel has a reasonable fixed-width range again
- artificial maximum widths on File Tools output, event table, and many spinboxes
  were removed
- the Series selector is widened again
