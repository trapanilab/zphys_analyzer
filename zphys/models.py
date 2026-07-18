from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class Sweep:
    """One sweep/episode with time in seconds and signal in native units."""

    y: np.ndarray
    x: np.ndarray | None = None
    name: str = ""
    units: str = ""
    sampling_interval: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def timebase(self) -> np.ndarray:
        if self.x is not None:
            return self.x
        if self.sampling_interval is None:
            return np.arange(self.y.size)
        return np.arange(self.y.size) * self.sampling_interval


@dataclass
class Series:
    """A SutterPatch/Igor 2D wave: rows=time, columns=sweeps/episodes."""

    name: str
    data: np.ndarray
    sampling_interval: float | None = None
    units: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def sweep_count(self) -> int:
        if self.data.ndim == 1:
            return 1
        return int(self.data.shape[1])

    @property
    def point_count(self) -> int:
        return int(self.data.shape[0])

    def sweep(self, index: int) -> Sweep:
        if self.data.ndim == 1:
            y = self.data
        else:
            y = self.data[:, index]
        return Sweep(
            y=np.asarray(y, dtype=float),
            name=f"{self.name}[{index + 1}]",
            units=self.units,
            sampling_interval=self.sampling_interval,
            metadata={**self.metadata, "series": self.name, "sweep_index": index},
        )


@dataclass
class Recording:
    """Normalized data container replacing Igor named waves/data folders."""

    path: Path | None
    source_format: str
    sweeps: list[Sweep] = field(default_factory=list)
    stimulus: list[Sweep] = field(default_factory=list)
    series: list[Series] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def sweep_count(self) -> int:
        if self.sweeps:
            return len(self.sweeps)
        return sum(s.sweep_count for s in self.series)

    def stack_sweeps(self) -> np.ndarray:
        if self.sweeps:
            min_len = min(s.y.size for s in self.sweeps)
            return np.column_stack([s.y[:min_len] for s in self.sweeps])
        if self.series:
            return self.series[0].data
        return np.empty((0, 0))

    def all_sweeps_from_series(self) -> list[Sweep]:
        if self.sweeps:
            return self.sweeps
        out: list[Sweep] = []
        for series in self.series:
            for i in range(series.sweep_count):
                out.append(series.sweep(i))
        return out
