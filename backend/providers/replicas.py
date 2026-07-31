"""
providers/replicas.py
=====================
Live Kubernetes replica count implementations.

Concrete classes
----------------
  KubernetesProvider   — queries the K8s API via kubectl for ready replica count
  NullReplicaProvider  — always returns None (uses static config count)
"""
from __future__ import annotations

import subprocess
import time

from .base import ReplicaProvider


class KubernetesProvider(ReplicaProvider):
    """
    Queries ``kubectl get deployment`` for the current ``readyReplicas`` count.
    Results are cached per app for ``cache_ttl`` seconds (default 5 min) since
    replica counts change infrequently.
    """

    def __init__(
        self,
        kubectl_path:    str,
        kubeconfig:      str,
        deployments:     dict[str, str],   # app_name → deployment name
        namespace:       str,
        cache_ttl:       int = 300,
    ) -> None:
        self._kubectl     = kubectl_path
        self._kubeconfig  = kubeconfig
        self._deployments = deployments
        self._namespace   = namespace
        self._cache_ttl   = cache_ttl
        self._cache: dict[str, tuple[int, float]] = {}   # app_name → (count, ts)

    def get_replica_count(self, app_name: str) -> int | None:
        if not self._kubeconfig or app_name not in self._deployments:
            return None

        cached = self._cache.get(app_name)
        if cached and (time.time() - cached[1]) < self._cache_ttl:
            return cached[0]

        deployment = self._deployments[app_name]
        cmd = [
            self._kubectl, "--kubeconfig", self._kubeconfig,
            "get", "deployment", deployment,
            "-n", self._namespace,
            "-o", "jsonpath={.status.readyReplicas}",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                count = int(result.stdout.strip())
                self._cache[app_name] = (count, time.time())
                return count
        except Exception as exc:
            print(f"[replicas] failed to get replica count for {app_name}: {exc}", flush=True)
        return None


class NullReplicaProvider(ReplicaProvider):
    """Always returns None — the SCI engine falls back to the static config count."""

    def get_replica_count(self, app_name: str) -> int | None:
        return None
