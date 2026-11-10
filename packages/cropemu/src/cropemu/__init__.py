"""cropemu: fast, validated emulators of process-based crop models.

>>> import cropemu
>>> cropemu.available()
['aquacrop-soybean-v1', 'dssat-soybean-v1']
>>> emu = cropemu.load("dssat-soybean-v1")
>>> emu.describe()                       # outputs, units, acceptance levels

Weather (NASA POWER, station data) and soil (SoilGrids, measured profiles) helpers are in
``cropemu.weather`` and ``cropemu.soil``; readers of DSSAT files (weather, soil, cultivars,
experiments, observations) in ``cropemu.io``.
"""

from .emulator import Emulator, Prediction, available, gdd_between, load, season_gdd

__all__ = ["Emulator", "Prediction", "available", "gdd_between", "load", "season_gdd"]

__version__ = "0.3.0"
