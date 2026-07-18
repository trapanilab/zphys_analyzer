# v76 histogram display fix

Display Spike/Event Histogram now:
- resets display/range state before plotting the histogram
- caps histogram bin count to avoid sluggish/blank displays
- applies explicit X/Y ranges after plotting
- hides the threshold line
- uses a visible bar style for the histogram
