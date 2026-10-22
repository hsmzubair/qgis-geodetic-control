# Changelog

## 0.1.1
- Fix: saved PostgreSQL connections were not listed on some QGIS builds. The dock now also reads the saved connection settings (as DB Manager does), refreshes the list when shown, and has a Refresh button.
- Clearer error message when the layer cannot be opened.

## 0.1.0
- PostGIS browser and editor with validation and a database edit history
- PROJ transformations: ETRF2000-PL, PL-1992, PL-2000 zones 5-8 (auto zone)
- Ellipsoidal to PL-EVRF2007-NH heights with the GUGiK geoid2021 grid
- GML export validated against an XSD schema
- pytest suite and GitHub Actions CI
