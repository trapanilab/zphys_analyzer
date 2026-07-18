# v14 layout and paired windows

## Cleaner analysis layout

The Analysis Tools tab now has internal subtabs:

- Detect
- Windows
- Actions

This keeps threshold/event detection controls separate from window generation and processing actions.

## Arbitrary frequencies

The window generator supports any frequency. Presets are available for common values, but the frequency box can be edited directly.

## Paired windows

Check:

```text
Generate two windows per cycle
```

Then set:

```text
Second window offset/gap (ms)
Second window width (ms)
```

For example, at 20 Hz the period is 50 ms. A paired window with offset 25 ms starts halfway through each stimulus cycle. Both windows remain draggable after generation.
