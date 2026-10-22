from datetime import date, timedelta

from lxml import etree

from geodetic_control_browser.core import gml_export
from geodetic_control_browser.core.model import ControlPoint, validate


def _point(**kw):
    base = dict(
        point_no="6612-0042",
        point_class="II",
        easting=566_000.123,
        northing=244_500.456,
        height=219.874,
        height_system="PL-EVRF2007-NH",
        status="active",
        last_surveyed=date(2025, 5, 14),
        description="Demo point",
    )
    base.update(kw)
    return ControlPoint(**base)


def test_valid_point_passes():
    assert validate(_point()).ok


def test_bad_point_number():
    r = validate(_point(point_no="66120042"))
    assert not r.ok and r.issues[0].field == "point_no"


def test_duplicate_point_number():
    r = validate(_point(), existing_numbers={"6612-0042"})
    assert not r.ok


def test_coordinates_outside_poland():
    r = validate(_point(easting=50_000.0))
    assert any(i.field == "easting" for i in r.issues)


def test_future_survey_date():
    r = validate(_point(last_surveyed=date.today() + timedelta(days=3)))
    assert any(i.field == "last_surveyed" for i in r.issues)


def test_legacy_height_is_warning_only():
    r = validate(_point(height_system="PL-KRON86-NH"))
    assert r.ok and any(i.severity == "warning" for i in r.issues)


def test_gml_document_validates():
    doc = gml_export.build_document([_point(), _point(point_no="6612-0043", height=None)])
    ok, errors = gml_export.validate_document(doc)
    assert ok, errors


def test_gml_rejects_duplicate_numbers():
    doc = gml_export.build_document([_point(), _point()])
    ok, errors = gml_export.validate_document(doc)
    assert not ok
    assert any("unique" in e.lower() or "duplicate" in e.lower() for e in errors)


def test_gml_rejects_bad_class():
    doc = gml_export.build_document([_point(point_class="IV")])
    ok, _ = gml_export.validate_document(doc)
    assert not ok


def test_export_writes_nothing_when_invalid(tmp_path):
    out = tmp_path / "bad.gml"
    ok, errors = gml_export.export([_point(point_class="X")], out)
    assert not ok and errors and not out.exists()


def test_export_round_trip(tmp_path):
    out = tmp_path / "points.gml"
    ok, _ = gml_export.export([_point()], out)
    assert ok and out.exists()
    ok, errors = gml_export.validate_file(out)
    assert ok, errors
    tree = etree.parse(str(out))
    pos = tree.find(".//{urn:demo:geodetic-control:1.0}position")
    assert pos.get("srsName") == "EPSG:2180"
    assert pos.text == "566000.123 244500.456"
