"""
providers/base.py
=================
Abstract Base Classes (interfaces) for all SCI data providers.

Each ABC defines a contract. Swap any implementation without touching the
SCI calculation engine — just pass a different concrete class instance.

Java analogy
------------
  GridIntensityProvider  ≈  interface GridIntensityProvider
  ElectricityMapsProvider ≈  class ElectricityMapsProvider implements GridIntensityProvider
"""
from __future__ import annotations
from abc import ABC, abstractmethod


class GridIntensityProvider(ABC):
    """
    Provides live (or static fallback) grid carbon intensity for a region.

    Returns a dict guaranteed to contain:
        intensity_gco2_kwh : float
        source             : str   e.g. "electricity-maps" | "watttime-v3" | "static-fallback"
        region             : str
    """

    @abstractmethod
    def get_intensity(
        self,
        em_zone: str | None,
        watttime_region: str | None,
        fallback_gco2: float,
    ) -> dict: ...

    @property
    def name(self) -> str:
        return self.__class__.__name__


class MetricsProvider(ABC):
    """
    Provides live CPU / memory / network metrics for a named application.

    Returns a dict with keys:
        cpu_utilization_percent    : float  (0-100)
        memory_utilization_percent : float  (0-100)
        network_egress_gbps        : float
        source                     : str
        timestamp                  : str  (ISO-8601)

    Return None when the provider has no data — the SCI engine will then
    fall back to static config values.
    """

    @abstractmethod
    def get_metrics(self, app_name: str) -> dict | None: ...

    @property
    def source_label(self) -> str:
        return self.__class__.__name__


class FunctionalUnitProvider(ABC):
    """
    Provides the functional unit count per hour for a named application.

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
