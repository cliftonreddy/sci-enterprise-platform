"""
providers/grid.py
=================
Grid carbon intensity implementations.

Concrete classes
----------------
  ElectricityMapsProvider  — live data from api.electricitymap.org
  WattTimeProvider         — live data from api.watttime.org (v3)
  StaticFallbackProvider   — always returns the region's static fallback value
"""
from __future__ import annotations

import time
import requests as http

from .base import GridIntensityProvider


_CACHE_TTL = 900  # 15 min — grid intensity changes slowly


class ElectricityMapsProvider(GridIntensityProvider):
    """Fetches live carbon intensity from the Electricity Maps v3 API."""

    def __init__(self, token: str, base_url: str = "https://api.electricitymap.org") -> None:
        self._token    = token
        self._base_url = base_url
        self._cache: dict[str, tuple[dict, float]] = {}  # zone → (result, ts)

    def get_intensity(
        self,
        em_zone: str | None,
        watttime_region: str | None,
        fallback_gco2: float,
    ) -> dict:
        if not em_zone or not self._token:
            return _static(fallback_gco2, em_zone)

        # check cache
        if em_zone in self._cache:
            result, ts = self._cache[em_zone]
            if time.time() - ts < _CACHE_TTL:
                return result

        try:
            r = http.get(
                f"{self._base_url}/v3/carbon-intensity/latest",
                headers={"auth-token": self._token},
                params={"zone": em_zone},
                timeout=8,
            )
            r.raise_for_status()
            data = r.json()
            ci = data.get("carbonIntensity")
            if ci is not None:
                result = {
                    "intensity_gco2_kwh": round(float(ci), 2),
                    "source":             "electricity-maps",
                    "region":             em_zone,
                    "is_estimated":       data.get("isEstimated", False),
                }
                self._cache[em_zone] = (result, time.time())
                return result
        except Exception as exc:
            print(f"[electricity-maps] API error for {em_zone}: {exc}", flush=True)

        return _static(fallback_gco2, em_zone)


class WattTimeProvider(GridIntensityProvider):
    """Fetches live marginal carbon intensity from the WattTime v3 API."""

    def __init__(
        self,
        username: str,
        password: str,
        base_url: str = "https://api.watttime.org",
    ) -> None:
        self._user     = username
        self._password = password
        self._base_url = base_url
        self._token: str | None = None
        self._token_ts  = 0.0
        self._token_ttl = 1800
        self._cache: dict[str, tuple[dict, float]] = {}

    # ── token management ──────────────────────────────────────────────────────
    def _login(self) -> str | None:
        if self._token and (time.time() - self._token_ts) < self._token_ttl:
            return self._token
        if not self._user or not self._password:
            return None
        try:
            r = http.get(
                f"{self._base_url}/v3/login",
                params={"username": self._user, "password": self._password},
                timeout=8,
            )
            r.raise_for_status()
            self._token    = r.json().get("token")
            self._token_ts = time.time()
            return self._token
        except Exception:
            return None

    def get_intensity(
        self,
        em_zone: str | None,
        watttime_region: str | None,
        fallback_gco2: float,
    ) -> dict:
        if not watttime_region:
            return _static(fallback_gco2, em_zone)

        if watttime_region in self._cache:
            result, ts = self._cache[watttime_region]
            if time.time() - ts < _CACHE_TTL:
                return result

        token = self._login()
        if token:
            try:
                r = http.get(
                    f"{self._base_url}/v3/forecast",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"region": watttime_region, "signal_type": "co2_moer"},
                    timeout=8,
                )
                r.raise_for_status()
                data = r.json().get("data", [])
                if data:
                    moer  = data[0]["value"]
                    g_kwh = moer * 0.453592 / 1000.0
                    result = {
                        "intensity_gco2_kwh": round(g_kwh, 2),
                        "source":             "watttime-v3",
                        "region":             watttime_region,
                        "moer_raw_lb_mwh":    moer,
                    }
                    self._cache[watttime_region] = (result, time.time())
                    return result
            except Exception as exc:
                print(f"[watttime] API error for {watttime_region}: {exc}", flush=True)

        return _static(fallback_gco2, watttime_region)


class StaticFallbackProvider(GridIntensityProvider):
    """Always returns the region's static fallback value. No network calls."""

    def get_intensity(
        self,
        em_zone: str | None,
        watttime_region: str | None,
        fallback_gco2: float,
    ) -> dict:
        return _static(fallback_gco2, em_zone or watttime_region)


# ── helpers ───────────────────────────────────────────────────────────────────

def _static(fallback_gco2: float, region: str | None) -> dict:
    return {
        "intensity_gco2_kwh": fallback_gco2,
        "source":             "static-fallback",
        "region":             region or "unknown",
    }
