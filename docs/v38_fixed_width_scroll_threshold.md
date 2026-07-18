# v38 fixed-width scroll behavior and thicker threshold line

## Left panel width

The left control panel is narrowed and constrained more aggressively. Tab content
is capped in width so it does not create an oversized sideways-pannable area.

## Trackpad horizontal panning

The tab scroll areas now use a `VerticalOnlyScrollArea` that ignores horizontal
trackpad/wheel movement and only applies vertical scrolling.

## Threshold line

The plotted threshold line pen width was increased again for better visibility.
