# v50 pyqtgraph compatibility fix

v49 added pyqtgraph fast plotting flags (`autoDownsample`, `clipToView`,
`downsampleMethod`) to speed up overlay/baseline redraws. On some
pyqtgraph/PySide versions, those flags can trigger:

`AttributeError: autoRangeEnabled`

This version keeps the display-only manual decimation added in v49, but removes
the version-sensitive pyqtgraph fast flags. Analysis data remain full-resolution.
