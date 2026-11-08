"""DSSAT experiment files (FileX, ``.SBX``) with one factor level per treatment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ._fmt import num, yyddd
from .soil import SoilProfile

#: Daily output groups of DSSAT and the FileX switch that turns each on.
#: growth: PlantGro, PlantN...; carbon: SoilOrg, C balance; water: SoilWat, ET;
#: nitrogen: SoilNi, N balance; mineral: P/K; disease: pests; chemical; operations.
OUTPUT_GROUPS = {"growth": "GROUT", "carbon": "CAOUT", "water": "WAOUT", "nitrogen": "NIOUT",
                 "mineral": "MIOUT", "disease": "DIOUT", "chemical": "CHOUT", "operations": "OPOUT"}
MAX_TREATMENTS = 99


@dataclass
class EnvironmentModification:
    """Climate perturbation applied by DSSAT during the run (FileX *ENVIRONMENT MODIFICATIONS)."""

    tmax_add: float = 0.0      # °C added to TMAX
    tmin_add: float = 0.0      # °C added to TMIN
    rain_factor: float = 1.0   # multiplier of RAIN
    srad_factor: float = 1.0   # multiplier of SRAD
    co2: float | None = None   # CO2 (ppm) replacing the CO2 series; None keeps it

    def to_line(self, level: int, start: date) -> str:
        """FileX line, Fortran format (I3, I5, 8(1X, A1, F4.0)); A add, M multiply, R replace."""
        co2 = ("R", self.co2) if self.co2 is not None else ("A", 0)
        fields = [("A", 0), ("M", self.srad_factor), ("A", self.tmax_add), ("A", self.tmin_add),
                  ("M", self.rain_factor), co2, ("A", 0), ("A", 0)]   # EDAY ERAD EMAX EMIN ERAIN ECO2 EDEW EWIND
        return f"{level:2d} {yyddd(start)}" + "".join(f" {c}{num(v, 4, 1)}" for c, v in fields)


@dataclass
class Treatment:
    """One simulated treatment. ``weather``, ``soil`` and ``cultivar`` are keys/IDs of the
    weather series, soil profiles and cultivars passed to :meth:`DSSAT.simulate`."""

    weather: str
    soil: str
    cultivar: str
    planting: date
    start: date | None = None          # simulation start; default: 30 days before planting
    seasons: int = 1                   # NYERS: consecutive seasons, same planting day each year
    water: bool = True                 # simulate the water balance (False: no water stress)
    irrigation: bool = False           # automatic irrigation (with water=True)
    nitrogen: bool = False             # simulate the N balance with biological N fixation
    initial_water: float = 0.5         # fraction of plant-available water at the start (0-1)
    population: float = 30.0           # plants/m²
    row_spacing: int = 50              # cm
    planting_depth: float = 4.0        # cm
    environment: EnvironmentModification | None = None
    co2_method: str = "M"              # M: Mauna Loa series; D: fixed 380 ppm; W: CCO2 of weather file
    evapotranspiration: str = "R"      # R: Priestley-Taylor; F: FAO-56 Penman-Monteith
    name: str = ""

    def __post_init__(self):
        if self.start is None:
            self.start = self.planting - timedelta(days=30)
        if self.start > self.planting:
            raise ValueError("simulation start must not be after planting")
        if not 0 <= self.initial_water <= 1:
            raise ValueError("initial_water must be in [0, 1]")
        if self.co2_method not in "MDW" or len(self.co2_method) != 1:
            raise ValueError("co2_method must be M, D or W")
        if self.evapotranspiration not in ("R", "F"):
            raise ValueError("evapotranspiration must be R or F")
        if self.irrigation and not self.water:
            raise ValueError("irrigation requires water=True")


def write_filex(path, treatments: list[Treatment], wsta: dict[str, str], soils: dict[str, SoilProfile],
                daily: tuple[str, ...] = (), overview: bool = True) -> None:
    """Write a FileX with one level of every factor per treatment (TRNO = position + 1).

    ``wsta`` maps each treatment's ``weather`` key to the WSTA code of its .WTH file.
    """
    if not 0 < len(treatments) <= MAX_TREATMENTS:
        raise ValueError(f"a FileX holds 1 to {MAX_TREATMENTS} treatments")
    unknown = set(daily) - set(OUTPUT_GROUPS)
    if unknown:
        raise ValueError(f"unknown daily output groups {unknown}; valid: {list(OUTPUT_GROUPS)}")
    vbose = "Y" if daily else ("N" if overview else "0")
    switches = {g: ("Y" if g in daily else "N") for g in OUTPUT_GROUPS}

    L = ["*EXP.DETAILS: CEMU0001SB cropemu", "",
         "*TREATMENTS                        -------------FACTOR LEVELS------------",
         "@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM"]
    for i, t in enumerate(treatments, 1):
        me = i if t.environment is not None else 0
        L.append(f"{i:2d} 1 0 0 {(t.name or f'T{i}')[:25]:<25s}{i:3d}{i:3d}  0{i:3d}{i:3d}  0  0  0  0  0"
                 f"{me:3d}  0{i:3d}")

    L += ["", "*CULTIVARS", "@C CR INGENO CNAME"]
    L += [f"{i:2d} SB {t.cultivar} cropemu" for i, t in enumerate(treatments, 1)]

    L += ["", "*FIELDS", "@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX   SLDP ID_SOIL    FLNAME"]
    for i, t in enumerate(treatments, 1):
        s = soils[t.soil]
        L.append(f"{i:2d} CEMU{i:04d} {wsta[t.weather]:<8s}   -99     0 DR000     0     0   -99 "
                 f"{s.texture[:5]:<5s}{num(s.depth, 6, 0)} {t.soil:<10s} -99")

    L += ["", "*INITIAL CONDITIONS"]
    for i, t in enumerate(treatments, 1):
        L += ["@C   PCR ICDAT  ICRT  ICND  ICRN  ICRE  ICWD ICRES ICREN ICREP ICRIP ICRID ICNAME",
              f"{i:2d}    SB {yyddd(t.start)}   -99   -99     1     1   -99     0  0.00   -99     0     0 -99",
              "@C  ICBL  SH2O  SNH4  SNO3"]
        for r in soils[t.soil].layers.itertuples():
            sh2o = r.slll + t.initial_water * (r.sdul - r.slll)
            L.append(f"{i:2d} {num(r.slb, 5, 0)} {num(sh2o, 5, 3)}   0.5   2.0")

    L += ["", "*PLANTING DETAILS",
          "@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  PLDP  PLWT  PAGE  PENV  PLPH  SPRL"
          "                        PLNAME"]
    for i, t in enumerate(treatments, 1):
        L.append(f"{i:2d} {yyddd(t.planting)}   -99 {num(t.population, 5, 1)} {num(t.population, 5, 1)}"
                 f"     S     R {int(t.row_spacing):5d}     0 {num(t.planting_depth, 5, 1)}   -99   -99   -99"
                 f"   -99     0                           -99")

    envs = [(i, t) for i, t in enumerate(treatments, 1) if t.environment is not None]
    if envs:
        L += ["", "*ENVIRONMENT MODIFICATIONS", "@E ODATE EDAY  ERAD  EMAX  EMIN  ERAIN ECO2  EDEW  EWIND ENVNAME"]
        L += [t.environment.to_line(i, t.start) for i, t in envs]

    L += ["", "*SIMULATION CONTROLS"]
    for i, t in enumerate(treatments, 1):
        harvest = t.planting + timedelta(days=330)
        L += ["@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL",
              f"{i:2d} GE          {t.seasons:5d}     1     S {yyddd(t.start)}  2150 {'cropemu':<25s} CRGRO",
              "@N OPTIONS     WATER NITRO SYMBI PHOSP POTAS DISES  CHEM  TILL   CO2",
              f"{i:2d} OP              {'Y' if t.water else 'N'}     {'Y' if t.nitrogen else 'N'}"
              f"     {'Y' if t.nitrogen else 'N'}     N     N     N     N     N     {t.co2_method}",
              "@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL",
              f"{i:2d} ME              M     M     E     {t.evapotranspiration}     R     C     R     1     P"
              f"     R     1",
              "@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS",
              f"{i:2d} MA              R     {'A' if t.irrigation else 'N'}     N     N     M",
              "@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT",
              f"{i:2d} OU              N     {'Y' if overview else 'N'}     Y     1"
              + "".join(f"     {switches[g]}" for g in ("growth", "carbon", "water", "nitrogen", "mineral",
                                                         "disease"))
              + f"     {vbose}" + "".join(f"     {switches[g]}" for g in ("chemical", "operations"))
              + "     A",
              "", "@  AUTOMATIC MANAGEMENT",
              "@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN",
              f"{i:2d} PL          {yyddd(t.planting)} {yyddd(t.planting)}    40   100    30    40    10",
              "@N IRRIGATION  IMDEP ITHRL ITHRU IROFF IMETH IRAMT IREFF",
              f"{i:2d} IR             30    50   100 IB001 IB001    10  1.00",
              "@N NITROGEN    NMDEP NMTHR NAMNT NCODE NAOFF",
              f"{i:2d} NI             30    50    25 IB001 IB001",
              "@N RESIDUES    RIPCN RTIME RIDEP",
              f"{i:2d} RE            100     1    20",
              "@N HARVEST     HFRST HLAST HPCNP HPCNR",
              f"{i:2d} HA              0 {yyddd(harvest)}   100     0", ""]
    path.write_text("\n".join(L) + "\n")
