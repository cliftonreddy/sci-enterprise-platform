"""
providers/__init__.py
=====================
Public surface of the providers package.

Usage
-----
    from providers import build_providers, Providers

    p = build_providers()          # configured from environment variables
    grid_result = p.grid.get_intensity(zone, wt_region, fallback)

Swapping a provider (e.g. in tests or for IF integration)
----------------------------------------------------------
    from providers import build_providers
    from providers.grid import StaticFallbackProvider

    p = build_providers()
    p.grid = StaticFallbackProvider()   # no network calls
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from .base import (
    FunctionalUnitProvider,
    GridIntensityProvider,
    MetricsProvider,
    ReplicaProvider,
)
from .functional_units import ADOProvider, ConfigEstimateProvider, GA4Provider
from .grid import ElectricityMapsProvider, StaticFallbackProvider, WattTimeProvider
from .metrics import NullMetricsProvider, PrometheusProvider
from .replicas import KubernetesProvider, NullReplicaProvider

__all__ = [
    # ABCs
    "GridIntensityProvider",
    "MetricsProvider",
    "FunctionalUnitProvider",
    "ReplicaProvider",
    # Grid
    "ElectricityMapsProvider",
    "WattTimeProvider",
    "StaticFallbackProvider",
    # Metrics
    "PrometheusProvider",
    "NullMetricsProvider",
    # Functional units
    "GA4Provider",
    "ADOProvider",
    "ConfigEstimateProvider",
    # Replicas
    "KubernetesProvider",
    "NullReplicaProvider",
    # Factory
    "Providers",
    "build_providers",
]


@dataclass
class Providers:
    """
    Container for all active provider instances.

    The SCI engine receives a ``Providers`` instance and calls each interface
    method without caring which concrete implementation is behind it.

    To swap an implementation at runtime:
        p = build_providers()
        p.grid = StaticFallbackProvider()
    """
    grid:             GridIntensityProvider
    metrics:          MetricsProvider
    functional_units: list[FunctionalUnitProvider]   # tried in priority order
    replicas:         ReplicaProvider


def build_providers(
    *,
    # Prometheus
    kubectl_path:     str | None = None,
    kubeconfig:       str | None = None,
    pod_prefix:       str | None = None,
    pod_patterns:     dict[str, str] | None = None,
    app_deployments:  dict[str, str] | None = None,
    app_namespace:    str = "agent-captive",
    # Grid
    grid_provider:    str | None = None,
    em_token:         str | None = None,
    wt_user:          str | None = None,
    wt_pass:          str | None = None,
    # GA4
    ga4_property_id:  str | None = None,
    # ADO
    ado_pat:          str | None = None,
    ado_org_list:     list[str] | None = None,
    ado_projects:     list[str] | None = None,
) -> Providers:
    """
    Build a ``Providers`` instance from the given parameters.
    All parameters fall back to the corresponding environment variables when
    not supplied, making this suitable for both production startup and tests.
    """

    # ── resolve from env when not supplied ────────────────────────────────────
    kubectl_path    = kubectl_path    or os.getenv("KUBECTL_PATH",      "kubectl")
    kubeconfig      = kubeconfig      or os.getenv("KUBECONFIG",        "")
    pod_prefix      = pod_prefix      or os.getenv("PROMETHEUS_POD",    "ucp-metrics")
    grid_provider   = grid_provider   or os.getenv("GRID_PROVIDER",     "electricitymaps").lower()
    em_token        = em_token        or os.getenv("ELECTRICITY_MAPS_TOKEN", "")
    wt_user         = wt_user         or os.getenv("WATTTIME_USER",     "")
    wt_pass         = wt_pass         or os.getenv("WATTTIME_PASS",     "")
    ga4_property_id = ga4_property_id or os.getenv("GA4_PROPERTY_ID",  "")
    ado_pat         = ado_pat         or os.getenv("ADO_PAT",           "")

    if ado_org_list is None:
        raw = os.getenv("ADO_ORGS", "")
        ado_org_list = [o.strip() for o in raw.split(",") if o.strip()] \
                       or ([os.getenv("ADO_ORG", "")] if os.getenv("ADO_ORG") else [])
    if ado_projects is None:
        raw = os.getenv("ADO_PROJECTS", "")
        ado_projects = [p.strip() for p in raw.split(",") if p.strip()]

    # ── grid ──────────────────────────────────────────────────────────────────
    if grid_provider == "watttime" and wt_user and wt_pass:
        grid: GridIntensityProvider = WattTimeProvider(wt_user, wt_pass)
    elif grid_provider == "electricitymaps" and em_token:
        grid = ElectricityMapsProvider(em_token)
    else:
        grid = StaticFallbackProvider()

    # ── metrics ───────────────────────────────────────────────────────────────
    if kubeconfig and pod_patterns:
        metrics: MetricsProvider = PrometheusProvider(
            kubectl_path         = kubectl_path,
            kubeconfig           = kubeconfig,
            pod_prefix           = pod_prefix,
            pod_patterns         = pod_patterns,
            app_namespace        = app_namespace,
        )
    else:
        metrics = NullMetricsProvider()

    # ── functional units — priority-ordered list ──────────────────────────────
    fu_list: list[FunctionalUnitProvider] = []
    if ado_pat and ado_org_list:
        fu_list.append(ADOProvider(pat=ado_pat, org_list=ado_org_list, projects=ado_projects))
    if ga4_property_id:
        fu_list.append(GA4Provider(property_id=ga4_property_id))
    fu_list.append(ConfigEstimateProvider())   # always last — never returns None

    # ── replicas ──────────────────────────────────────────────────────────────
    if kubeconfig and app_deployments:
        replicas: ReplicaProvider = KubernetesProvider(
            kubectl_path = kubectl_path,
            kubeconfig   = kubeconfig,
            deployments  = app_deployments,
            namespace    = app_namespace,
        )
    else:
        replicas = NullReplicaProvider()

    return Providers(
        grid             = grid,
        metrics          = metrics,
        functional_units = fu_list,
        replicas         = replicas,
    )
