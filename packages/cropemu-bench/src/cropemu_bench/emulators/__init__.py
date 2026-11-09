"""Emulators sharing fit(X, Y, groups) / predict(X) on DataFrames."""

from .base import Emulator
from .mlp import MLPEmulator
from .sk import GBEmulator, RidgeEmulator

__all__ = ["Emulator", "MLPEmulator", "GBEmulator", "RidgeEmulator"]
