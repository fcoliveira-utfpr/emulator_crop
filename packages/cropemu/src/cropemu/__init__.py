"""cropemu: fast, validated emulators of process-based crop models.

>>> import cropemu
>>> cropemu.available()
['aquacrop-soybean-v1', 'dssat-soybean-v1']
>>> emu = cropemu.load("dssat-soybean-v1")
>>> emu.describe()                       # outputs, units, acceptance levels

Weather (NASA POWER) and soil (SoilGrids) helpers are in ``cropemu.weather`` and ``cropemu.soil``.
"""

from .emulator import Emulator, Prediction, available, load, season_gdd

__all__ = ["Emulator", "Prediction", "available", "load", "season_gdd"]

__version__ = "0.1.0"
