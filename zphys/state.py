from __future__ import annotations

from dataclasses import dataclass

from .models import Recording


@dataclass
class ZPhysState:
    """Python replacement for Igor root:A globals."""

    recording: Recording | None = None
    tempfolder: str = ""
    tempfilefolder: str = ""
    tempwave: str = ""
    input_type: str = ""
    stim_type: str = ""
    data_type: str = ""

    tempfreq: float = 5.0
    interval: float = 0.0
    dinterval: float = 0.0
    protocol: int = 1

    spikeamp: float = 0.0
    spiketime: float = 0.0
    eventamp: float = 0.0

    sweep_start: int = 1
    sweep_end: int = 60
    sweep_current: int = 1

    extra_gain: str = "no"
    extra_gain1: float = 500.0
    extra_gain2: float = 100.0

    @property
    def tempstep1(self) -> float:
        return 1.0 / self.tempfreq if self.tempfreq else 0.0

    @property
    def tempstep2(self) -> float:
        return 1.0 / self.tempfreq if self.tempfreq else 0.0
