# v41 dynamic panel width

The outer left-panel scroll area has been removed again so the header/common
controls remain fixed and the panel can resize with the app window.

Each tab still has its own vertical-only scroll area, and that scroll area's
content width is synchronized to the viewport width. This keeps tab contents from
being clipped while suppressing horizontal scrolling/panning.
