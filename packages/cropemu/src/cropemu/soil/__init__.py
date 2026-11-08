"""Soil profiles in the cropemu standard format.

A soil profile is a ``pandas.DataFrame`` with one row per layer:

==========  ===========================================================
top         layer top depth, cm
bottom      layer bottom depth, cm
clay        clay, % (mass)
sand        sand, % (mass)
silt        silt, % (mass)
soc         soil organic carbon, % (mass)
bdod        bulk density of the fine earth, g/cm³
cfvo        coarse fragments, % (volume)
nitrogen    total nitrogen, % (mass)
phh2o       pH in water
cec         cation exchange capacity, cmol(c)/kg
ll          water content at -1500 kPa (lower limit), cm³/cm³
dul         water content at -33 kPa (drained upper limit), cm³/cm³
sat         water content at saturation, cm³/cm³
ksat        saturated hydraulic conductivity, cm/h
==========  ===========================================================

``ll``, ``dul``, ``sat`` and ``ksat`` are added by :func:`cropemu.soil.ptf.hydraulics`.
Site information goes in ``df.attrs`` (``lat``, ``lon``, ``source``).
"""

from .ptf import hydraulics, saxton_rawls, texture_class

__all__ = ["hydraulics", "saxton_rawls", "texture_class"]
