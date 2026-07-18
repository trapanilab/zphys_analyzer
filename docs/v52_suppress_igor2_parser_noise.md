# v52 suppress Igor/PXP parser console noise

Some malformed-but-skippable Igor packed records cause igor2 to print messages
such as:

`could not reshape data from [np.int64(5)] to b''`

These messages are harmless for the tolerant SutterPatch loader but made command
line launch look like an error. The loader now redirects stdout/stderr around
igor2 record construction and filesystem building, while still storing skipped
record details in the parse report metadata.
