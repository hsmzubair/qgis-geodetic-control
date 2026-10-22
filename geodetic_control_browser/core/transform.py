"""Coordinate and height transformations for Polish geodetic data.

Pure Python + pyproj (no QGIS imports) so it can be unit-tested outside QGIS.

Horizontal systems (ETRF2000-PL based):
    EPSG:9702  ETRF2000-PL geographic 2D (lat/lon)
    EPSG:2180  CS92 (PL-1992)
    EPSG:2176-2179  CS2000 zones 5-8 (PL-2000, central meridians 15/18/21/24 E)

Vertical:
    EPSG:9701  ETRF2000-PL geographic 3D (ellipsoidal height)
    EPSG:9651  EVRF2007-PL height (PL-EVRF2007-NH)
    EPSG:9650  Baltic 1986 height (PL-KRON86-NH)

The ellipsoidal -> PL-EVRF2007-NH conversion uses the GUGiK geoid model grid
``pl_gugik_geoid2021-PL-EVRF2007-NH.tif`` from the PROJ data catalogue
(open licence). Install it with ``projsync --file pl_gugik_geoid2021-PL-EVRF2007-NH.tif``
or place it in the PROJ data directory.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from pyproj import CRS, Transformer
from pyproj.transformer import TransformerGroup

ETRF2000_PL_2D = "EPSG:9702"
ETRF2000_PL_3D = "EPSG:9701"
PL_1992 = "EPSG:2180"
PL_2000 = {5: "EPSG:2176", 6: "EPSG:2177", 7: "EPSG:2178", 8: "EPSG:2179"}
PL_EVRF2007_NH = "EPSG:9651"
PL_KRON86_NH = "EPSG:9650"

GEOID_2021_EVRF2007 = "pl_gugik_geoid2021-PL-EVRF2007-NH.tif"

HORIZONTAL_SYSTEMS = {
    "ETRF2000-PL (lat/lon)": ETRF2000_PL_2D,
    "PL-1992": PL_1992,
    "PL-2000 zone 5 (15E)": PL_2000[5],
    "PL-2000 zone 6 (18E)": PL_2000[6],
    "PL-2000 zone 7 (21E)": PL_2000[7],
    "PL-2000 zone 8 (24E)": PL_2000[8],
}

# Rough bounding box of Poland in ETRF2000-PL lat/lon, used for sanity checks.
POLAND_BBOX = (14.0, 48.9, 24.2, 55.0)  # min_lon, min_lat, max_lon, max_lat


class TransformationError(RuntimeError):
    """Raised when no usable transformation exists (e.g. a grid is missing)."""


@dataclass
class GridInfo:
    short_name: str
    available: bool
    url: str = ""


@dataclass
class OperationInfo:
    name: str
    accuracy_m: Optional[float]
    available: bool
    grids: List[GridInfo] = field(default_factory=list)

    @property
    def missing_grids(self) -> List[GridInfo]:
        return [g for g in self.grids if not g.available]


def pl2000_zone_for_longitude(lon: float) -> int:
    """Return the PL-2000 zone (5-8) whose central meridian is closest to ``lon``."""
    if not 13.5 <= lon <= 24.5:
        raise ValueError(f"Longitude {lon} is outside the PL-2000 zones")
    if lon < 16.5:
        return 5
    if lon < 19.5:
        return 6
    if lon < 22.5:
        return 7
    return 8


def pl2000_crs_for_longitude(lon: float) -> str:
    return PL_2000[pl2000_zone_for_longitude(lon)]


def list_operations(src: str, dst: str) -> List[OperationInfo]:
    """List candidate operations between two CRSs, best first, with grid status."""
    group = TransformerGroup(src, dst, always_xy=True)
    ops: List[OperationInfo] = []
    for t in group.transformers:
        ops.append(OperationInfo(t.description, _accuracy(t.accuracy), True, []))
    for op in group.unavailable_operations:
        grids = [GridInfo(g.short_name, g.available, g.url) for g in op.grids]
        ops.append(OperationInfo(op.name, _accuracy(op.accuracy), False, grids))
    return ops


def _accuracy(value) -> Optional[float]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v >= 0 else None


def build_transformer(src: str, dst: str, *, require_best: bool = True) -> Transformer:
    """Return the best available transformer.

    With ``require_best=True`` a :class:`TransformationError` is raised when the most
    accurate operation needs a grid that is not installed, instead of silently
    falling back to a less accurate (often ballpark) operation.
    """
    group = TransformerGroup(src, dst, always_xy=True)
    if require_best and not group.best_available:
        missing = sorted(
            {g.short_name for op in group.unavailable_operations for g in op.grids if not g.available}
        )
        raise TransformationError(
            f"Best transformation {src} -> {dst} needs missing grid(s): {', '.join(missing)}. "
            f"Install with: projsync --file <grid name>"
        )
    if not group.transformers:
        raise TransformationError(f"No transformation available {src} -> {dst}")
    return group.transformers[0]


def transform_xy(
    points: Iterable[Tuple[float, float]], src: str, dst: str, *, require_best: bool = True
) -> List[Tuple[float, float]]:
    """Transform (x, y) pairs. Geographic input/output is (lon, lat)."""
    tr = build_transformer(src, dst, require_best=require_best)
    out = []
    for x, y in points:
        tx, ty = tr.transform(x, y, errcheck=True)
        out.append((tx, ty))
    return out


def geoid_pipeline(grid: str | Path) -> str:
    """PROJ pipeline: ETRF2000-PL lon/lat/ellipsoidal h (degrees, metres) ->
    lon/lat/normal height, using a geoid grid (H = h - N)."""
    return (
        "+proj=pipeline "
        "+step +proj=unitconvert +xy_in=deg +xy_out=rad "
        f"+step +proj=vgridshift +grids={grid} +multiplier=-1 "
        "+step +proj=unitconvert +xy_in=rad +xy_out=deg"
    )


def ellipsoidal_to_normal_height(
    lon: float, lat: float, h_ellipsoidal: float, grid: str | Path = GEOID_2021_EVRF2007
) -> float:
    """Convert an ellipsoidal height (ETRF2000-PL) to a normal height using a geoid grid.

    By default uses the GUGiK geoid2021 model for PL-EVRF2007-NH. Pass an absolute
    path to use a local grid file.
    """
    tr = Transformer.from_pipeline(geoid_pipeline(grid))
    _, _, h = tr.transform(lon, lat, h_ellipsoidal, errcheck=True)
    return float(h)


def in_poland(lon: float, lat: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = POLAND_BBOX
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def crs_label(code: str) -> str:
    return f"{code} - {CRS.from_user_input(code).name}"


def summarize(ops: Sequence[OperationInfo]) -> str:
    lines = []
    for op in ops:
        acc = f"{op.accuracy_m:.3f} m" if op.accuracy_m is not None else "unknown"
        state = "available" if op.available else "MISSING GRID"
        lines.append(f"[{state}] {op.name} (accuracy {acc})")
        for g in op.missing_grids:
            lines.append(f"    needs: {g.short_name}  {g.url}")
    return "\n".join(lines)
