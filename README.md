# Geodetic Control Browser (QGIS plugin)

A QGIS 3 plugin for working with geodetic control points stored in PostGIS:
browse and edit points with validation, convert coordinates between Polish
national systems with PROJ, convert ellipsoidal heights to PL-EVRF2007-NH with
the GUGiK geoid model, and export GML that is validated against an XSD schema.

> **Status:** demo / portfolio project (v0.1.0). The sample data is fictional.

![Dock widget](docs/dock_preview.png)

*Dock UI rendered from `ui/control_dock.ui` with the fictional sample data.*

## Features

| Area | What it does |
|---|---|
| **PostGIS browser** | Loads `gc.control_point` from any saved PostGIS connection, styles points by status, search and status filter, table and map selection kept in sync. |
| **Editing** | Edit point number, class, status, height and height system, survey date and description. Validation runs before saving (`core/model.py`), and the database enforces the same rules with CHECK constraints. |
| **Edit history** | A database trigger writes every insert, update and delete to `gc.control_point_history` (old and new rows as JSON). The **History** button shows the field-level changes. |
| **Coordinate transformation** | PROJ via pyproj: ETRF2000-PL lat/lon (EPSG:9702), PL-1992 (EPSG:2180) and PL-2000 zones 5–8 (EPSG:2176–2179), with automatic zone selection. **Show operations** lists candidate operations with accuracy and any missing grids. |
| **No silent fallback** | If the most accurate operation needs a grid that is not installed, the transform stops and names the grid instead of quietly using a less accurate "ballpark" operation. |
| **Heights** | Ellipsoidal (ETRF2000-PL) to normal heights in PL-EVRF2007-NH (EPSG:9651) with the GUGiK `pl_gugik_geoid2021-PL-EVRF2007-NH.tif` grid. |
| **GML export** | GML-style feature collection with CRS-tagged positions, validated against `schemas/geodetic_control.xsd` (types, enumerations, patterns, unique point numbers). Nothing is written if validation fails. |

## Repository layout

```
geodetic_control_browser/
  __init__.py          QGIS classFactory
  plugin.py            toolbar button, menu, dock toggle
  control_dock.py      dock logic (QGIS API)
  ui/control_dock.ui   Qt Designer form
  core/                pure Python, no QGIS imports (unit-tested)
    model.py           control point model + validation rules
    transform.py       PROJ pipelines, PL-2000 zones, geoid heights
    gml_export.py      GML build, XSD validation, export
  schemas/geodetic_control.xsd
  sql/schema.sql       PostGIS tables, constraints, history trigger
  sql/sample_data.sql  8 fictional points near Krakow
tests/                 pytest suite for core/
```

## Install

1. **Database:** create a PostGIS database and run
   `psql -d <db> -f geodetic_control_browser/sql/schema.sql -f geodetic_control_browser/sql/sample_data.sql`.
2. **QGIS connection:** add the database in the QGIS Browser panel (PostgreSQL → New Connection).
3. **Plugin:** zip the `geodetic_control_browser` folder (or run `python scripts/package.py`) and use
   *Plugins → Manage and Install Plugins → Install from ZIP*.
4. **Geoid grid** (for height conversion):
   ```
   projsync --file pl_gugik_geoid2021-PL-EVRF2007-NH.tif
   ```
   or download it from https://cdn.proj.org/pl_gugik_geoid2021-PL-EVRF2007-NH.tif into your PROJ data directory.

Requires QGIS 3.28 or later; pyproj and lxml ship with standard QGIS installs.

## Tests

The core logic has no QGIS dependency, so it runs in plain Python:

```
pip install -r requirements-dev.txt
pytest
```

The suite covers PL-2000 zone selection, PL-1992/PL-2000 round trips, detection
of missing geoid grids, a geoid height conversion with a synthetic grid
(H = h − N), point validation rules, and GML generation and XSD validation
(including rejection of duplicates and invalid values). CI runs it on every push
(`.github/workflows/tests.yml`).

## Notes and limitations

- The XSD is a self-contained demo application schema that follows the GML
  feature-collection pattern. A production system would validate against the
  official GML 3.2.1 and GUGiK/PZGiK application schemas through a local XML catalog.
- Transformation accuracy depends on the installed grids; results should be
  checked against surveyed control before production use.
- Point numbering (`NNNN-NNNN`) and the sample points are illustrative only.

## License

GPL-2.0-or-later (required for plugins in the official QGIS repository). See `LICENSE`.
