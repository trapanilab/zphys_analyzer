# v77 ISI histogram

Display Spike/Event Histogram now plots inter-spike intervals (ISIs), not raw
event times.

ISIs are calculated as:
`spike_time(n+1) - spike_time(n)`

Intervals are computed within each source/series/sweep/trace/window group so an
interval never crosses from one sweep/window/trace into another.
