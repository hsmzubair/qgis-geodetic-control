"""Export control points to GML-style XML and validate against the XSD (no QGIS dependency)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from lxml import etree

from .model import ControlPoint

NS = "urn:demo:geodetic-control:1.0"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "geodetic_control.xsd"


def _q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def build_document(points: Iterable[ControlPoint], producer: str = "Geodetic Control Browser") -> etree._ElementTree:
    pts = list(points)
    root = etree.Element(_q("ControlPointCollection"), nsmap={"gc": NS})
    md = etree.SubElement(root, _q("metadata"))
    etree.SubElement(md, _q("createdAt")).text = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    etree.SubElement(md, _q("producer")).text = producer
    etree.SubElement(md, _q("featureCount")).text = str(len(pts))

    for p in pts:
        member = etree.SubElement(root, _q("featureMember"))
        cp = etree.SubElement(member, _q("ControlPoint"), id=f"CP_{p.point_no.replace('-', '_')}")
        etree.SubElement(cp, _q("pointNo")).text = p.point_no
        etree.SubElement(cp, _q("pointClass")).text = p.point_class
        pos = etree.SubElement(cp, _q("position"), srsName=p.crs)
        pos.text = f"{p.easting:.3f} {p.northing:.3f}"
        if p.height is not None:
            h = etree.SubElement(cp, _q("height"), system=p.height_system or "PL-EVRF2007-NH", uom="m")
            h.text = f"{p.height:.3f}"
        etree.SubElement(cp, _q("status")).text = p.status
        if p.last_surveyed:
            etree.SubElement(cp, _q("lastSurveyed")).text = p.last_surveyed.isoformat()
        if p.description:
            etree.SubElement(cp, _q("description")).text = p.description
    return etree.ElementTree(root)


def load_schema(path: Path = SCHEMA_PATH) -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(str(path)))


def validate_document(doc: etree._ElementTree, schema: etree.XMLSchema | None = None) -> Tuple[bool, List[str]]:
    schema = schema or load_schema()
    ok = schema.validate(doc)
    errors = [f"line {e.line}: {e.message}" for e in schema.error_log] if not ok else []
    return ok, errors


def export(points: Sequence[ControlPoint], out_path: str | Path, *, validate: bool = True) -> Tuple[bool, List[str]]:
    """Write the GML file. If validation fails, nothing is written and errors are returned."""
    doc = build_document(points)
    if validate:
        ok, errors = validate_document(doc)
        if not ok:
            return False, errors
    doc.write(str(out_path), xml_declaration=True, encoding="UTF-8", pretty_print=True)
    return True, []


def validate_file(path: str | Path) -> Tuple[bool, List[str]]:
    return validate_document(etree.parse(str(path)))
