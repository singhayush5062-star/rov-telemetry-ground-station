"""OpenStreetMap view embedded with QWebEngineView + Leaflet (gui/map.html)."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

_HTML = Path(__file__).with_name("map.html")


class MapView(QWebEngineView):
    ready = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ready = False
        self._pending: tuple[float, float, float] | None = None
        self._pending_origin: str | None = None
        # map.html is a local file. Chromium blocks remote sub-resources (OSM
        # tiles) from file:// pages unless LocalContentCanAccessRemoteUrls is on,
        # and once that is on, Qt 6.12 also needs LocalContentCanAccessFileUrls
        # set explicitly or the local vendor/leaflet script silently fails.
        st = self.settings()
        st.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        st.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self.loadFinished.connect(self._on_loaded)
        self.load(QUrl.fromLocalFile(str(_HTML)))

    def _on_loaded(self, ok: bool) -> None:
        self._ready = ok
        self.ready.emit(ok)
        if ok and self._pending_origin:
            self.page().runJavaScript(self._pending_origin)
        if ok and self._pending:
            self.update_rov(*self._pending)

    def update_rov(self, lat: float, lon: float, heading_deg: float) -> None:
        if not self._ready:
            self._pending = (lat, lon, heading_deg)
            return
        self.page().runJavaScript(f"updateRov({lat:.7f}, {lon:.7f}, {heading_deg:.2f});")

    def clear_trail(self) -> None:
        if self._ready:
            self.page().runJavaScript("clearTrail();")

    def set_origin(self, lat: float, lon: float, label: str) -> None:
        js = f"setOrigin({lat:.7f}, {lon:.7f}, {json.dumps(label)});"
        if self._ready:
            self.page().runJavaScript(js)
        else:
            self._pending_origin = js
