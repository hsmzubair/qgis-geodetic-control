"""QGIS plugin entry point: adds a toolbar button and menu item that toggle the dock."""
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

MENU = "&Geodetic Control"


class GeodeticControlPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock = None

    def initGui(self):  # noqa: N802 (QGIS API name)
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icons", "icon.svg"))
        self.action = QAction(icon, "Geodetic Control Browser", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.toggled.connect(self.toggle_dock)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToDatabaseMenu(MENU, self.action)

    def unload(self):
        self.iface.removePluginDatabaseMenu(MENU, self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dock:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None

    def toggle_dock(self, checked):
        if checked and self.dock is None:
            from .control_dock import ControlDockWidget  # import lazily so QGIS starts fast

            self.dock = ControlDockWidget(self.iface, self.iface.mainWindow())
            self.dock.visibilityChanged.connect(self.action.setChecked)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        if self.dock:
            self.dock.setVisible(checked)
