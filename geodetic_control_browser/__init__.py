"""Geodetic Control Browser QGIS plugin."""


def classFactory(iface):  # noqa: N802 (QGIS API name)
    from .plugin import GeodeticControlPlugin

    return GeodeticControlPlugin(iface)
