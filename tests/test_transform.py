import struct

import pytest

from geodetic_control_browser.core import transform as t


@pytest.mark.parametrize(
    "lon,zone",
    [(14.5, 5), (16.4, 5), (17.0, 6), (19.94, 7), (18.6, 6), (21.0, 7), (22.6, 8), (23.9, 8)],
)
def test_pl2000_zone(lon, zone):
    assert t.pl2000_zone_for_longitude(lon) == zone


def test_pl2000_zone_outside_poland():
    with pytest.raises(ValueError):
        t.pl2000_zone_for_longitude(30.0)


def test_pl1992_round_trip():
    # Krakow Main Market Square (approx.), ETRF2000-PL lon/lat
    lon, lat = 19.9373, 50.0617
    [(x, y)] = t.transform_xy([(lon, lat)], t.ETRF2000_PL_2D, t.PL_1992)
    assert 560_000 < x < 575_000 and 240_000 < y < 250_000
    [(lon2, lat2)] = t.transform_xy([(x, y)], t.PL_1992, t.ETRF2000_PL_2D)
    assert lon2 == pytest.approx(lon, abs=1e-8)
    assert lat2 == pytest.approx(lat, abs=1e-8)


def test_pl1992_to_pl2000_krakow_is_zone_7():
    lon, lat = 19.9373, 50.0617
    [(x92, y92)] = t.transform_xy([(lon, lat)], t.ETRF2000_PL_2D, t.PL_1992)
    zone_crs = t.pl2000_crs_for_longitude(lon)
    [(e, n)] = t.transform_xy([(x92, y92)], t.PL_1992, zone_crs)
    # Krakow (19.94E) lies in zone 7 (19.5-22.5E); false easting 7,500,000 m
    assert zone_crs == t.PL_2000[7]
    assert 7_400_000 < e < 7_500_000
    assert 5_500_000 < n < 5_600_000


def test_operations_report_missing_geoid_grid():
    ops = t.list_operations(t.ETRF2000_PL_3D, t.PL_EVRF2007_NH)
    names = {g.short_name for op in ops for g in op.grids}
    assert t.GEOID_2021_EVRF2007 in names


def _write_gtx(path, value, lat0=48.0, lon0=13.0, step=1.0, rows=9, cols=13):
    """Write a constant-value NOAA .gtx vertical grid (big-endian)."""
    with open(path, "wb") as f:
        f.write(struct.pack(">4d2i", lat0, lon0, step, step, rows, cols))
        f.write(struct.pack(f">{rows * cols}f", *([value] * rows * cols)))


def test_geoid_height_conversion_with_local_grid(tmp_path):
    grid = tmp_path / "test_geoid.gtx"
    _write_gtx(grid, 30.0)  # constant geoid undulation N = 30 m
    h_normal = t.ellipsoidal_to_normal_height(19.9373, 50.0617, 250.0, grid=grid)
    assert h_normal == pytest.approx(220.0, abs=1e-3)  # H = h - N


def test_build_transformer_refuses_ballpark_when_grid_missing():
    with pytest.raises(t.TransformationError) as exc:
        t.build_transformer(t.ETRF2000_PL_3D, t.PL_EVRF2007_NH, require_best=True)
    assert t.GEOID_2021_EVRF2007 in str(exc.value)
