# v31 signal dropdown startup fix

Fixed a startup crash from the compact header connecting the Signal dropdown to
`_signal_filter_changed` when that compatibility slot was not present.

The app now provides `_signal_filter_changed` as a wrapper around the available
series-refresh method in this version of the code.

Also verifies sweep navigation wrappers are present for the compact header
previous/next buttons.
