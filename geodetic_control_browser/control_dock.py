"""Dock widget: browse, edit, transform and export geodetic control points from PostGIS."""
from __future__ import annotations

import json
import os
from datetime import date

from qgis.core import (
    Qgis,
    QgsCategorizedSymbolRenderer,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDataSourceUri,
    QgsFeatureRequest,
    QgsMarkerSymbol,
    QgsProject,
    QgsProviderRegistry,
    QgsRectangle,
    QgsRendererCategory,
    QgsVectorLayer,
)
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QDate, Qt
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem

from .core import gml_export
from .core import transform as tr
from .core.model import HEIGHT_SYSTEMS, POINT_CLASSES, STATUSES, ControlPoint, validate

FORM_CLASS, BASE_CLASS = uic.loadUiType(os.path.join(os.path.dirname(__file__), "ui", "control_dock.ui"))

SCHEMA, TABLE, GEOM_COL, KEY_COL = "gc", "control_point", "geom", "id"
COLUMNS = ["point_no", "point_class", "status", "height", "height_system", "last_surveyed"]
STATUS_COLOURS = {"active": "#1a7f37", "damaged": "#d4a017", "destroyed": "#c62828", "not_found": "#7b7b7b"}


class ControlDockWidget(BASE_CLASS, FORM_CLASS):
    """Dock built from ui/control_dock.ui (Qt Designer)."""

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.layer: QgsVectorLayer | None = None
        self.connection = None
        self._fill_static_combos()
        self._fill_connections()
        self._connect_signals()
        self._set_edit_enabled(False)

    # ---------------------------------------------------------------- setup
    def _fill_static_combos(self):
        self.classCombo.addItems(POINT_CLASSES)
        self.statusCombo.addItems(STATUSES)
        self.heightSystemCombo.addItems(HEIGHT_SYSTEMS)
        self.statusFilter.addItem("All statuses", "")
        for s in STATUSES:
            self.statusFilter.addItem(s, s)
        for label, code in tr.HORIZONTAL_SYSTEMS.items():
            self.targetCombo.addItem(label, code)
        self.targetCombo.addItem("PL-2000 (auto zone)", "PL2000_AUTO")
        self.surveyedDate.setMaximumDate(QDate.currentDate())

    def _fill_connections(self):
        self.connCombo.clear()
        md = QgsProviderRegistry.instance().providerMetadata("postgres")
        for name in sorted(md.connections().keys()):
            self.connCombo.addItem(name)
        if self.connCombo.count() == 0:
            self.log("No PostGIS connections found. Add one in the Browser panel first.")

    def _connect_signals(self):
        self.loadButton.clicked.connect(self.load_layer)
        self.searchEdit.textChanged.connect(self.refresh_table)
        self.statusFilter.currentIndexChanged.connect(self.refresh_table)
        self.pointsTable.itemSelectionChanged.connect(self.on_selection_changed)
        self.hasHeightCheck.toggled.connect(self.heightSpin.setEnabled)
        self.hasHeightCheck.toggled.connect(self.heightSystemCombo.setEnabled)
        self.saveButton.clicked.connect(self.save_current)
        self.zoomButton.clicked.connect(self.zoom_to_current)
        self.historyButton.clicked.connect(self.show_history)
        self.opsButton.clicked.connect(self.show_operations)
        self.transformButton.clicked.connect(self.transform_selected)
        self.heightButton.clicked.connect(self.convert_heights)
        self.exportButton.clicked.connect(self.export_gml)

    # ------------------------------------------------------------- helpers
    def log(self, text: str):
        self.messagesText.appendPlainText(text)

    def _set_edit_enabled(self, enabled: bool):
        for w in (self.editGroup, self.transformGroup, self.exportButton):
            w.setEnabled(enabled)

    def _selected_fids(self):
        rows = sorted({i.row() for i in self.pointsTable.selectedIndexes()})
        return [self.pointsTable.item(r, 0).data(Qt.UserRole) for r in rows]

    def _feature_to_point(self, f) -> ControlPoint:
        g = f.geometry().asPoint()
        surveyed = f["last_surveyed"]
        if surveyed and hasattr(surveyed, "toPyDate"):
            surveyed = surveyed.toPyDate()
        height = f["height"]
        return ControlPoint(
            fid=f.id(),
            point_no=f["point_no"],
            point_class=f["point_class"],
            easting=g.x(),
            northing=g.y(),
            crs=self.layer.crs().authid(),
            height=float(height) if height not in (None, "") and str(height) != "NULL" else None,
            height_system=f["height_system"] or None,
            status=f["status"],
            last_surveyed=surveyed or None,
            description=f["description"] or "",
        )

    # ---------------------------------------------------------------- load
    def load_layer(self):
        name = self.connCombo.currentText()
        if not name:
            return
        md = QgsProviderRegistry.instance().providerMetadata("postgres")
        self.connection = md.connections()[name]
        uri = QgsDataSourceUri(self.connection.uri())
        uri.setDataSource(SCHEMA, TABLE, GEOM_COL, "", KEY_COL)
        layer = QgsVectorLayer(uri.uri(False), "Geodetic control points", "postgres")
        if not layer.isValid():
            self.log(f"Could not open {SCHEMA}.{TABLE} on '{name}'. Run sql/schema.sql first.")
            return
        self._style_layer(layer)
        QgsProject.instance().addMapLayer(layer)
        self.layer = layer
        self.layer.selectionChanged.connect(self._sync_map_selection)
        self.refresh_table()
        self._set_edit_enabled(True)
        self.log(f"Loaded {layer.featureCount()} points from '{name}' ({layer.crs().authid()}).")

    def _style_layer(self, layer):
        cats = []
        for status, colour in STATUS_COLOURS.items():
            sym = QgsMarkerSymbol.createSimple({"name": "triangle", "color": colour, "size": "3.2"})
            cats.append(QgsRendererCategory(status, sym, status))
        layer.setRenderer(QgsCategorizedSymbolRenderer("status", cats))

    def refresh_table(self):
        if not self.layer:
            return
        text = self.searchEdit.text().strip().lower()
        status = self.statusFilter.currentData()
        self.pointsTable.setSortingEnabled(False)
        self.pointsTable.clear()
        self.pointsTable.setColumnCount(len(COLUMNS))
        self.pointsTable.setHorizontalHeaderLabels(COLUMNS)
        rows = []
        for f in self.layer.getFeatures():
            if status and f["status"] != status:
                continue
            hay = f"{f['point_no']} {f['description'] or ''}".lower()
            if text and text not in hay:
                continue
            rows.append(f)
        self.pointsTable.setRowCount(len(rows))
        for r, f in enumerate(rows):
            for c, col in enumerate(COLUMNS):
                v = f[col]
                item = QTableWidgetItem("" if v is None or str(v) == "NULL" else str(v))
                if c == 0:
                    item.setData(Qt.UserRole, f.id())
                self.pointsTable.setItem(r, c, item)
        self.pointsTable.setSortingEnabled(True)
        self.pointsTable.resizeColumnsToContents()

    # ---------------------------------------------------------- selection
    def on_selection_changed(self):
        fids = self._selected_fids()
        if self.layer:
            self.layer.selectByIds(fids)
        if len(fids) != 1:
            return
        f = self.layer.getFeature(fids[0])
        p = self._feature_to_point(f)
        self.pointNoEdit.setText(p.point_no)
        self.classCombo.setCurrentText(p.point_class)
        self.statusCombo.setCurrentText(p.status)
        self.hasHeightCheck.setChecked(p.height is not None)
        self.heightSpin.setValue(p.height or 0.0)
        self.heightSpin.setEnabled(p.height is not None)
        self.heightSystemCombo.setCurrentText(p.height_system or "PL-EVRF2007-NH")
        self.heightSystemCombo.setEnabled(p.height is not None)
        if p.last_surveyed:
            self.surveyedDate.setDate(QDate(p.last_surveyed.year, p.last_surveyed.month, p.last_surveyed.day))
        self.descriptionEdit.setText(p.description)

    def _sync_map_selection(self, selected, deselected, clear_and_select):
        # Keep the table in sync when the user selects points on the map.
        wanted = set(self.layer.selectedFeatureIds())
        self.pointsTable.blockSignals(True)
        self.pointsTable.clearSelection()
        for r in range(self.pointsTable.rowCount()):
            if self.pointsTable.item(r, 0).data(Qt.UserRole) in wanted:
                self.pointsTable.selectRow(r)
        self.pointsTable.blockSignals(False)

    # --------------------------------------------------------------- edit
    def save_current(self):
        fids = self._selected_fids()
        if len(fids) != 1:
            self.log("Select exactly one point to edit.")
            return
        fid = fids[0]
        f = self.layer.getFeature(fid)
        g = f.geometry().asPoint()
        d = self.surveyedDate.date()
        p = ControlPoint(
            fid=fid,
            point_no=self.pointNoEdit.text(),
            point_class=self.classCombo.currentText(),
            easting=g.x(),
            northing=g.y(),
            crs=self.layer.crs().authid(),
            height=self.heightSpin.value() if self.hasHeightCheck.isChecked() else None,
            height_system=self.heightSystemCombo.currentText() if self.hasHeightCheck.isChecked() else None,
            status=self.statusCombo.currentText(),
            last_surveyed=date(d.year(), d.month(), d.day()),
            description=self.descriptionEdit.text().strip(),
        )
        others = {x["point_no"] for x in self.layer.getFeatures() if x.id() != fid}
        result = validate(p, existing_numbers=others)
        for issue in result.issues:
            self.log(str(issue))
        if not result.ok:
            self.iface.messageBar().pushMessage("Not saved", "Fix the validation errors first.", Qgis.Warning, 5)
            return

        values = {
            "point_no": p.point_no,
            "point_class": p.point_class,
            "status": p.status,
            "height": p.height,
            "height_system": p.height_system,
            "last_surveyed": p.last_surveyed.isoformat() if p.last_surveyed else None,
            "description": p.description or None,
        }
        fields = self.layer.fields()
        attr_map = {fields.indexOf(k): v for k, v in values.items()}
        self.layer.startEditing()
        self.layer.changeAttributeValues(fid, attr_map)
        if self.layer.commitChanges():
            self.log(f"Saved {p.point_no}. The database logged the change in gc.control_point_history.")
            self.refresh_table()
        else:
            errors = "; ".join(self.layer.commitErrors())
            self.layer.rollBack()
            self.log(f"Database rejected the change: {errors}")

    def zoom_to_current(self):
        fids = self._selected_fids()
        if not fids:
            return
        canvas = self.iface.mapCanvas()
        xform = QgsCoordinateTransform(self.layer.crs(), canvas.mapSettings().destinationCrs(), QgsProject.instance())
        box = QgsRectangle()
        for f in self.layer.getFeatures(QgsFeatureRequest().setFilterFids(fids)):
            box.combineExtentWith(xform.transformBoundingBox(f.geometry().boundingBox()))
        box.grow(0.002 if canvas.mapSettings().destinationCrs().isGeographic() else 150)  # padding
        canvas.setExtent(box)
        canvas.refresh()

    def show_history(self):
        fids = self._selected_fids()
        if len(fids) != 1 or not self.connection:
            return
        point_id = int(self.layer.getFeature(fids[0])[KEY_COL])
        rows = self.connection.executeSql(
            "SELECT changed_at, changed_by, operation, old_row, new_row "
            f"FROM {SCHEMA}.control_point_history WHERE point_id = {point_id} "
            "ORDER BY changed_at DESC LIMIT 20"
        )
        if not rows:
            self.log("No history for this point.")
            return
        self.log(f"History for point id {point_id}:")
        for changed_at, by, op, old, new in rows:
            diff = _diff(old, new)
            self.log(f"  {changed_at}  {by}  {op}  {diff}")

    # ---------------------------------------------------------- transform
    def show_operations(self):
        target = self._target_code(None)
        if target is None:
            return
        src = self.layer.crs().authid()
        self.log(f"Operations {src} -> {target}:")
        self.log(tr.summarize(tr.list_operations(src, target)))

    def _target_code(self, lon):
        code = self.targetCombo.currentData()
        if code == "PL2000_AUTO":
            if lon is None:
                self.log("PL-2000 (auto zone) picks the zone per point; showing zone 7 operations.")
                return tr.PL_2000[7]
            return tr.pl2000_crs_for_longitude(lon)
        return code

    def transform_selected(self):
        fids = self._selected_fids()
        if not fids:
            self.log("Select one or more points first.")
            return
        src = self.layer.crs().authid()
        try:
            for f in self.layer.getFeatures(QgsFeatureRequest().setFilterFids(fids)):
                pt = f.geometry().asPoint()
                [(lon, lat)] = tr.transform_xy([(pt.x(), pt.y())], src, tr.ETRF2000_PL_2D)
                target = self._target_code(lon)
                [(x, y)] = tr.transform_xy([(pt.x(), pt.y())], src, target)
                fmt = "{:.8f}" if QgsCoordinateReferenceSystem(target).isGeographic() else "{:.3f}"
                self.log(f"{f['point_no']}: {target}  x={fmt.format(x)}  y={fmt.format(y)}")
        except tr.TransformationError as e:
            self.log(str(e))

    def convert_heights(self):
        fids = self._selected_fids()
        src = self.layer.crs().authid()
        done = 0
        for f in self.layer.getFeatures(QgsFeatureRequest().setFilterFids(fids)):
            if f["height_system"] != "ellipsoidal":
                continue
            pt = f.geometry().asPoint()
            [(lon, lat)] = tr.transform_xy([(pt.x(), pt.y())], src, tr.ETRF2000_PL_2D)
            try:
                h = tr.ellipsoidal_to_normal_height(lon, lat, float(f["height"]))
            except Exception as e:  # pyproj raises ProjError when the grid is missing
                self.log(f"Geoid grid unavailable ({tr.GEOID_2021_EVRF2007}): {e}")
                self.log("Install it with: projsync --file " + tr.GEOID_2021_EVRF2007)
                return
            self.log(f"{f['point_no']}: h={float(f['height']):.3f} m (ellipsoidal) -> H={h:.3f} m PL-EVRF2007-NH")
            done += 1
        if done == 0:
            self.log("No selected points have ellipsoidal heights.")

    # ------------------------------------------------------------- export
    def export_gml(self):
        if not self.layer:
            return
        fids = self._selected_fids()
        req = QgsFeatureRequest().setFilterFids(fids) if fids else QgsFeatureRequest()
        points = [self._feature_to_point(f) for f in self.layer.getFeatures(req)]
        path, _ = QFileDialog.getSaveFileName(self, "Export GML", "control_points.gml", "GML (*.gml)")
        if not path:
            return
        ok, errors = gml_export.export(points, path, validate=True)
        if ok:
            self.log(f"Exported {len(points)} points to {path} (valid against geodetic_control.xsd).")
        else:
            self.log("Export stopped: the document is not valid against the XSD.")
            for e in errors[:20]:
                self.log("  " + e)
            QMessageBox.warning(self, "GML not exported", "Validation failed. See the messages panel.")


def _diff(old, new) -> str:
    old = json.loads(old) if isinstance(old, str) else (old or {})
    new = json.loads(new) if isinstance(new, str) else (new or {})
    changed = [k for k in sorted(set(old) | set(new)) if old.get(k) != new.get(k) and k not in ("updated_at",)]
    return ", ".join(f"{k}: {old.get(k)} -> {new.get(k)}" for k in changed) or "(no field changes)"
