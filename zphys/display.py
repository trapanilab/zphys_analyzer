from __future__ import annotations

from pathlib import Path

import numpy as np


def current_sweep_index(requested_one_based: int, sweep_count: int) -> int:
    """Clamp Igor-style 1-based sweep number and return Python 0-based index."""

    if sweep_count <= 0:
        return 0
    return max(0, min(requested_one_based - 1, sweep_count - 1))


def save_binary(path: str | Path, y: np.ndarray) -> None:
    np.asarray(y).tofile(path)
