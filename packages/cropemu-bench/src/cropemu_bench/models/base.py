"""Common interface of the crop model adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class SimulationResult:
    """Outputs of a batch of simulations, with native variable names.

    Attributes
    ----------
    summary
        One row per simulated season. Always has ``treatment`` (index of the
        treatment in the input list) and ``season`` (0-based season within the
        treatment), followed by every variable the model reports per season.
    daily
        Daily output tables keyed by file/group name (e.g. ``"PlantGro"``).
        Each has ``treatment`` and ``season`` columns plus the model's columns.
    extra
        Other per-season tables (e.g. DSSAT ``OVERVIEW.OUT`` stress factors),
        keyed by name, with ``treatment`` and ``season`` columns.
    """

    summary: pd.DataFrame
    daily: dict[str, pd.DataFrame] = field(default_factory=dict)
    extra: dict[str, pd.DataFrame] = field(default_factory=dict)


class CropModel(ABC):
    """A crop model that simulates batches of treatments."""

    name: str

    @abstractmethod
    def simulate(self, treatments, **inputs) -> SimulationResult:
        """Simulate every treatment and return all outputs."""
