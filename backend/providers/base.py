"""
providers/base.py
=================
Abstract Base Classes (interfaces) for all SCI data providers, plus the
TypedDicts that define the exact return-shape contract for each interface.

A new provider MUST subclass the right ABC and return the matching TypedDict.
If the wrong keys are returned, mypy / pyright will catch it before runtime.

Java analogy
------------
  GridIntensityProvider   ≈  interface GridIntensityProvider
  GridIntensityResult     ≈  record / DTO GridIntensityResult
  ElectricityMapsProvider ≈  class ElectricityMapsProvider implements GridIntensityProvider
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import NotRequired, TypedDict


# ── Return-shape contracts ────────────────────────────────────────────────────

class GridIntensityResult(TypedDict):
    """
    Guaranteed fields every GridIntensityProvider implementation must return.
    Optional fields are present only when the provider supplies them.
    """
    intensity_gco2_kwh: float       # gCO2 per kWh, always present
    source:             str         # "electricity-maps" | "watttime-v3" | "static-fallback"
    region:             str         # zone / region identifier used for the lookup
    is_estimated:       NotRequired[bool]   # ElectricityMaps marginal-vs-average flag
    moer_raw_lb_mwh:    NotRequired[float]  # WattTime raw value before unit conversion


class MetricsResult(TypedDict):
    """
    Guaranteed fields every MetricsProvider implementation must return
    (when it returns a result rather than None).
    """
    cpu_utilization_percent:    float   # 0 – 100
    memory_utilization_percent: float   # 0 – 100
    network_egress_gbps:        float
    source:                     str     # e.g. "prometheus-live" | "static-config"
    timestamp:                  str     # ISO-8601


# ── Abstract Base Classes (interfaces) ───────────────────────────────────────

class GridIntensityProvider(ABC):
    """
    Provides live (or static fallback) grid carbon intensity for a region.

    Implementors must return a GridIntensityResult — the three required keys
    (intensity_gco2_kwh, source, region) must always be present.
    """

    @abstractmethod
    def get_intensity(
        self,
        em_zone: str | None,
        watttime_region: str | None,
        fallback_gco2: float,
    ) -> GridIntensityResult: ...

    @property
    def name(self) -> str:
        return self.__class__.__name__


class MetricsProvider(ABC):
    """
    Provides live CPU / memory / network metrics for a named application.

    Return None when the provider has no data — the SCI engine will then
    fall back to static config values.
    Implementors must return a MetricsResult (or None).
    """

    @abstractmethod
    def get_metrics(self, app_name: str) -> MetricsResult | None: ...

    @property
    def source_label(self) -> str:
        return self.__class__.__name__


class FunctionalUnitProvider(ABC):
    """
    Provides the functional unit count (requests, builds, views…) per hour
    for a named application.

    Return None when:
      - The provider does not cover this app (e.g. ADO provider for a web app)
      - Credentials are not configured
      - The upstream API call fails

    The SCI engine walks a priority-ordered list of providers and uses the
    first non-None result.
    """

    @abstractmethod
    def get_units_per_hour(self, app_name: str, config: dict) -> float | None: ...

    @property
    def source_label(self) -> str:
        return self.__class__.__name__


class ReplicaProvider(ABC):
    """
    Provides the current live replica (pod) count for a named application.

    Return None to signal "use the static count from config".
    """

    @abstractmethod
    def get_replica_count(self, app_name: str) -> int | None: ...

    @property
    def name(self) -> str:
        return self.__class__.__name__
