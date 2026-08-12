"""
providers/metrics.py
====================
Application CPU / memory / network metrics implementations.

Concrete classes
----------------
  PrometheusProvider  — live metrics via kubectl exec into MKE ucp-metrics pod
  NullMetricsProvider — always returns None (disables live metrics)
"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.parse
from datetime import datetime, timezone

from .base import MetricsProvider, MetricsResult


class PrometheusProvider(MetricsProvider):
    """
    Fetches live CPU, memory, and network metrics from the Mirantis MKE
    Prometheus instance by exec-ing curl inside a ucp-metrics pod.

    Pod discovery is automatic: if ``pod_prefix`` does not exactly match a
    running pod, the provider searches for any Running pod whose name starts
    with ``pod_prefix + "-"`` in ``prometheus_namespace``.  The resolved name
    is cached for ``pod_cache_ttl`` seconds so the cluster API is not hit on
    every request.
    """

    def __init__(
        self,
        kubectl_path:        str,
        kubeconfig:          str,
        pod_prefix:          str,
        pod_patterns:        dict[str, str],   # app_name → pod name prefix
        app_namespace:       str,
        prometheus_namespace: str              = "kube-system",
        prometheus_url:      str               = "https://localhost:9090",
        container_name:      str               = "ucp-metrics-prometheus",
        cert:                str               = "/node_certs/cert.pem",
        key:                 str               = "/node_certs/key.pem",
        ca:                  str               = "/node_certs/ca.pem",
        query_timeout:       int               = 5,
        pod_cache_ttl:       int               = 300,
    ) -> None:
        self._kubectl      = kubectl_path
        self._kubeconfig   = kubeconfig
        self._pod_prefix   = pod_prefix
        self._pod_patterns = pod_patterns
        self._app_ns       = app_namespace
        self._prom_ns      = prometheus_namespace
        self._prom_url     = prometheus_url
        self._container    = container_name
        self._cert         = cert
        self._key          = key
        self._ca           = ca
        self._timeout      = query_timeout
        self._pod_ttl      = pod_cache_ttl

        self._resolved_pod:    str | None = None
        self._resolved_pod_ts: float      = 0.0

    # ── MetricsProvider interface ─────────────────────────────────────────────

    @property
    def source_label(self) -> str:
        return "prometheus-live"

    def get_metrics(self, app_name: str) -> MetricsResult | None:
        if not self._kubeconfig or app_name not in self._pod_patterns:
            return None

        pod_re = self._pod_patterns[app_name] + ".*"
        ns     = self._app_ns
        sel    = f'podNamespace="{ns}",podName=~"{pod_re}",podContainerName!="POD"'
        net_sel = f'podNamespace="{ns}",podName=~"{pod_re}"'

        cpu    = self._scalar(self._query(f'avg(ucp_engine_container_cpu_percent{{{sel},type="cpu"}})'))
        mem    = self._scalar(self._query(f'avg(ucp_engine_container_memory_usage_percent{{{sel}}})'))
        net_gb = self._scalar(self._query(
            f'(sum(rate(ucp_engine_container_network_rx_bytes_total{{{net_sel}}}[1h]))'
            f' + sum(rate(ucp_engine_container_network_tx_bytes_total{{{net_sel}}}[1h])))'
            f' * 3600 / 1e9'
        ))

        if cpu is None and mem is None:
            return None

        return {
            "cpu_utilization_percent":    round(max(cpu    or 0.0, 0.0), 1),
            "memory_utilization_percent": round(min(max(mem or 0.0, 0.0), 100.0), 1),
            "network_egress_gbps":        round((net_gb or 0.0) / 3600.0, 6),
            "source":                     self.source_label,
            "timestamp":                  datetime.now(timezone.utc).isoformat(),
        }

    # ── pod discovery ─────────────────────────────────────────────────────────

    def resolve_pod(self) -> str | None:
        if self._resolved_pod and (time.time() - self._resolved_pod_ts) < self._pod_ttl:
            return self._resolved_pod
        try:
            result = subprocess.run(
                [self._kubectl, "--kubeconfig", self._kubeconfig,
                 "get", "pods", "-n", self._prom_ns,
                 "--field-selector=status.phase=Running",
                 "-o", "jsonpath={.items[*].metadata.name}"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                print(f"[prometheus] pod discovery failed: {result.stderr.strip()}", flush=True)
                return None
            prefix = self._pod_prefix
            match  = next(
                (p for p in result.stdout.split() if p == prefix or p.startswith(prefix + "-")),
                None,
            )
            if match:
                if match != self._resolved_pod:
                    print(f"[prometheus] resolved pod: {match}", flush=True)
                self._resolved_pod    = match
                self._resolved_pod_ts = time.time()
                return match
            print(f"[prometheus] no Running pod matching '{prefix}' in {self._prom_ns}", flush=True)
            return None
        except Exception as exc:
            print(f"[prometheus] pod discovery error: {exc}", flush=True)
            return None

    # ── low-level query helpers ───────────────────────────────────────────────

    def _query(self, promql: str) -> list:
        pod = self.resolve_pod()
        if not pod:
            return []
        encoded = urllib.parse.quote(promql, safe="")
        url     = f"{self._prom_url}/api/v1/query?query={encoded}"
        cmd = [
            self._kubectl, "--kubeconfig", self._kubeconfig,
            "exec", "-n", self._prom_ns, pod,
            "-c", self._container, "--",
            "curl", "-s",
            "--cert",   self._cert,
            "--key",    self._key,
            "--cacert", self._ca,
            url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self._timeout)
            if result.returncode != 0:
                print(f"[prometheus] exec failed (rc={result.returncode}): {result.stderr.strip()}", flush=True)
                return []
            data = json.loads(result.stdout)
            return data.get("data", {}).get("result", [])
        except subprocess.TimeoutExpired:
            print(f"[prometheus] exec timed out after {self._timeout}s", flush=True)
            return []
        except Exception as exc:
            print(f"[prometheus] unexpected error: {exc}", flush=True)
            return []

    @staticmethod
    def _scalar(results: list) -> float | None:
        if not results:
            return None
        try:
            return float(results[0]["value"][1])
        except (IndexError, KeyError, ValueError):
            return None


class NullMetricsProvider(MetricsProvider):
    """Always returns None — effectively disables live metrics (uses static config)."""

    @property
    def source_label(self) -> str:
        return "static-config"

    def get_metrics(self, app_name: str) -> MetricsResult | None:
        return None
