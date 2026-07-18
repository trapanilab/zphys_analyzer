# v32 series dropdown startup fix

Fixed a startup crash from the compact header connecting the Series dropdown to
`update_series_controls` when that method was not present in this code version.

The compact header now connects Series changes to `_series_selection_changed`,
which is a compatibility wrapper. It calls the available series-change method if
one exists, otherwise it updates sweep limits and redraws the current plot.
