"""
Operator location for the launch origin.

Resolution order (first success wins):
  1. --origin LAT,LON on the command line / ROV_ORIGIN env var   ("manual")
  2. The OS location service via QtPositioning                   ("GPS/OS location")
       - real GPS receiver where present, otherwise Wi-Fi / cell positioning
         (Windows Location, macOS CoreLocation, geoclue2 on Linux)
  3. IP-based geolocation over HTTPS (city-level, ~km accuracy)   ("IP geolocation")
       - ipapi.co, then ipinfo.io
  4. DEFAULT_ORIGIN from the simulator                           ("default")

Each stage has a timeout so the application never waits on a location; the
map simply re-centres when a fix arrives.  Only stage 3 contacts a third
party (it sees the machine's public IP, which is inherent to the method).
"""
from __future__ import annotations

import json
import os

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from rov_sim.simulator import DEFAULT_ORIGIN

try:
    from PySide6.QtPositioning import QGeoPositionInfoSource
except ImportError:                     # positioning module missing -> skip stage 2
    QGeoPositionInfoSource = None

OS_LOCATION_TIMEOUT_MS = 8000
HTTP_TIMEOUT_MS = 6000
IP_SERVICES = ["https://ipapi.co/json/", "https://ipinfo.io/json"]


def parse_origin_arg(text: str | None) -> tuple[float, float] | None:
    """'28.6654,77.4391' -> (28.6654, 77.4391); None/invalid -> None."""
    if not text:
        return None
    try:
        lat_s, lon_s = text.split(",")
        lat, lon = float(lat_s), float(lon_s)
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def parse_ip_geolocation(payload: bytes | str) -> tuple[float, float, str] | None:
    """Accept either ipapi.co ({latitude, longitude, city, country_code}) or
    ipinfo.io ({loc: "lat,lon", city, country}) JSON. Returns (lat, lon, place)."""
    try:
        d = json.loads(payload)
    except (ValueError, TypeError):
        return None
    if not isinstance(d, dict):
        return None
    try:
        if "loc" in d:
            lat, lon = (float(v) for v in d["loc"].split(","))
        else:
            lat, lon = float(d["latitude"]), float(d["longitude"])
    except (KeyError, ValueError, TypeError, AttributeError):
        return None
    parts = []
    if d.get("city"):
        parts.append(str(d["city"]))
    country = d.get("country_name") or d.get("country_code") or d.get("country")
    if country:
        parts.append(str(country))
    return lat, lon, ", ".join(parts) or "unknown place"


class LocationProvider(QObject):
    located = Signal(float, float, str)   # lat, lon, human-readable source

    def __init__(self, manual: tuple[float, float] | None = None, parent=None):
        super().__init__(parent)
        self._manual = manual
        self._src = None
        self._nam = QNetworkAccessManager(self)
        self._done = False
        self._services = list(IP_SERVICES)

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._manual:
            self._finish(*self._manual, "manual (--origin)")
        elif QGeoPositionInfoSource is not None:
            self._try_os_location()
        else:
            self._try_ip_geolocation()

    def _finish(self, lat: float, lon: float, source: str) -> None:
        if self._done:
            return
        self._done = True
        if self._src is not None:
            self._src.stopUpdates()
        self.located.emit(lat, lon, source)

    # ---------------------------------------------------- stage 2: OS / GPS
    def _try_os_location(self) -> None:
        self._src = QGeoPositionInfoSource.createDefaultSource(self)
        if self._src is None:
            self._try_ip_geolocation(); return
        self._src.positionUpdated.connect(self._on_position)
        self._src.errorOccurred.connect(lambda *_: self._try_ip_geolocation())
        self._src.requestUpdate(OS_LOCATION_TIMEOUT_MS)
        QTimer.singleShot(OS_LOCATION_TIMEOUT_MS + 500, self._try_ip_geolocation)  # belt and braces

    def _on_position(self, info) -> None:
        c = info.coordinate()
        if c.isValid():
            self._finish(c.latitude(), c.longitude(), f"GPS/OS location ({self._src.sourceName()})")

    # ---------------------------------------------------- stage 3: IP lookup
    def _try_ip_geolocation(self) -> None:
        if self._done:
            return
        if not self._services:
            self._finish(*DEFAULT_ORIGIN, "default (no location available)"); return
        url = self._services.pop(0)
        req = QNetworkRequest(QUrl(url))
        req.setHeader(QNetworkRequest.UserAgentHeader, "ROVGroundStation/1.0")
        req.setTransferTimeout(HTTP_TIMEOUT_MS)
        reply = self._nam.get(req)
        reply.finished.connect(lambda: self._on_ip_reply(reply))

    def _on_ip_reply(self, reply: QNetworkReply) -> None:
        data = bytes(reply.readAll()) if reply.error() == QNetworkReply.NetworkError.NoError else b""
        reply.deleteLater()
        parsed = parse_ip_geolocation(data) if data else None
        if parsed:
            lat, lon, place = parsed
            self._finish(lat, lon, f"IP geolocation ({place})")
        else:
            self._try_ip_geolocation()      # next service, or default
