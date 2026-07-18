# v22 checkbox word-wrap fix

Fixed a PySide6 startup crash caused by calling `setWordWrap(True)` on a
`QCheckBox`. PySide6 checkboxes do not implement that method.

The main baseline checkbox is now shorter:

```text
Apply baseline to all selected sweeps
```

A separate wrapped QLabel explains when it applies.
