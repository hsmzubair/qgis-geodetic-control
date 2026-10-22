"""Control point data model and validation rules (no QGIS dependency)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

POINT_CLASSES = ("I", "II", "III")
STATUSES = ("active", "damaged", "destroyed", "not_found")
HEIGHT_SYSTEMS = ("PL-EVRF2007-NH", "PL-KRON86-NH", "ellipsoidal")

# Demo numbering convention: 4-digit sheet code + "-" + 4-digit sequence, e.g. 6612-0042.
POINT_NO_RE = re.compile(r"^\d{4}-\d{4}$")

# Plausible ranges in PL-1992 (EPSG:2180), metres.
PL1992_X_RANGE = (140_000.0, 900_000.0)   # easting
PL1992_Y_RANGE = (120_000.0, 800_000.0)   # northing
HEIGHT_RANGE = (-10.0, 2_500.0)           # Poland: about -2 m (Zulawy) to 2,499 m (Rysy)


@dataclass
class ControlPoint:
    point_no: str
    point_class: str
    easting: float
    northing: float
    crs: str = "EPSG:2180"
    height: Optional[float] = None
    height_system: Optional[str] = "PL-EVRF2007-NH"
    status: str = "active"
    last_surveyed: Optional[date] = None
    description: str = ""
    fid: Optional[int] = None


@dataclass
class Issue:
    field: str
    message: str
    severity: str = "error"  # error | warning

    def __str__(self) -> str:
        return f"{self.severity.upper()}: {self.field}: {self.message}"


@dataclass
class ValidationResult:
    issues: List[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def add(self, field_name: str, message: str, severity: str = "error") -> None:
        self.issues.append(Issue(field_name, message, severity))


def validate(p: ControlPoint, existing_numbers: Optional[set] = None) -> ValidationResult:
    r = ValidationResult()

    if not POINT_NO_RE.match(p.point_no or ""):
        r.add("point_no", f"'{p.point_no}' does not match NNNN-NNNN")
    elif existing_numbers and p.point_no in existing_numbers:
        r.add("point_no", f"'{p.point_no}' already exists")

    if p.point_class not in POINT_CLASSES:
        r.add("point_class", f"must be one of {', '.join(POINT_CLASSES)}")

    if p.status not in STATUSES:
        r.add("status", f"must be one of {', '.join(STATUSES)}")

    if p.crs == "EPSG:2180":
        if not PL1992_X_RANGE[0] <= p.easting <= PL1992_X_RANGE[1]:
            r.add("easting", f"{p.easting:.2f} is outside the PL-1992 range for Poland")
        if not PL1992_Y_RANGE[0] <= p.northing <= PL1992_Y_RANGE[1]:
            r.add("northing", f"{p.northing:.2f} is outside the PL-1992 range for Poland")

    if p.height is not None:
        if p.height_system not in HEIGHT_SYSTEMS:
            r.add("height_system", f"must be one of {', '.join(HEIGHT_SYSTEMS)}")
        if not HEIGHT_RANGE[0] <= p.height <= HEIGHT_RANGE[1]:
            r.add("height", f"{p.height:.3f} m is outside the plausible range for Poland")
        if p.height_system == "PL-KRON86-NH":
            r.add("height_system", "legacy Kronstadt 86 height; convert to PL-EVRF2007-NH", "warning")
    elif p.point_class in ("I", "II"):
        r.add("height", "class I/II points should have a height", "warning")

    if p.last_surveyed and p.last_surveyed > date.today():
        r.add("last_surveyed", "date is in the future")

    if p.status == "destroyed" and not p.description:
        r.add("description", "explain why the point is marked destroyed", "warning")

    return r
