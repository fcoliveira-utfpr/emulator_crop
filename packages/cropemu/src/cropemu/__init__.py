"""cropemu: fast, validated emulators of process-based crop models.

``cropemu.load`` (exported emulators: ONNX graph + card), weather and soil helpers
(NASA POWER, SoilGrids) and the input computation shared with ``cropemu-bench``.
Nothing is published yet.
"""

from .emulator import Emulator, Prediction, load

__all__ = ["Emulator", "Prediction", "load"]

__version__ = "0.0.1"
