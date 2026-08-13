"""
Enterprise Multi-Application SCI Platform Backend
================================================
Calculates SCI scores for multiple applications with different hardware configs,
provides optimization recommendations (hardware changes, region relocation, time-shifting).

Architecture:
  - Loads server specs from JSON (real AWS/Azure/GCP instance types)
  - Loads app configs + hourly metrics from CSV
  - Calculates full SCI pipeline for each app
  - WattTime v3 multi-region carbon intensity
  - Optimization engine: brute-force all region+server combinations
  - Recommendations: carbon threshold, cost-carbon tradeoff, time-shifting
"""

from __future__ import annotations

import json, os, time, csv, traceback, subprocess
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from collections import defaultdict

from flask import Flask, Response, jsonify, request
from flask_cors import CORS
import requests as http

from providers import (
    Providers, build_providers,
    ADOProvider, GA4Provider,
)

# ── app ───────────────────────────────────────────────────────────────────────
app  = Flask(__name__)
CORS(app)

# ── paths ─────────────────────────────────────────────────────────────────────
# Try Docker path first, fall back to relative path for local dev
_docker_data = Path("/app/data")
_local_data = Path(__file__).parent.parent / "data"
DATA_DIR = _docker_data if _docker_data.exists() else _local_data

SERVERS_DIR     = DATA_DIR / "servers"
NETWORK_DIR     = DATA_DIR / "network"
APPS_DIR        = DATA_DIR / "apps"
REGIONS_FILE    = DATA_DIR / "regions" / "grid-regions.json"

# ── WattTime v3 ───────────────────────────────────────────────────────────────
WT_USER         = os.getenv("WATTTIME_USER", "")
WT_PASS         = os.getenv("WATTTIME_PASS", "")
WT_BASE         = "https://api.watttime.org"
_WT_TOKEN       = None
_WT_TOKEN_TS    = 0.0
_WT_TOKEN_TTL   = 1800



# ── Electricity Maps v3 ──────────────────────────────────────────────────────
EM_TOKEN        = os.getenv("ELECTRICITY_MAPS_TOKEN", "")
EM_BASE         = "https://api.electricitymap.org"

# ── Grid provider selection ──────────────────────────────────────────────────
# GRID_PROVIDER=electricitymaps | watttime  (falls back to static-fallback if API fails)
GRID_PROVIDER   = os.getenv("GRID_PROVIDER", "electricitymaps").lower()

# GA4_PROPERTY_ID kept for startup logging; actual cache lives in GA4Provider instance
GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "")

# ── Azure DevOps CI/CD ────────────────────────────────────────────────────────
# ADO_ORGS:       comma-separated collection/org names
#                 e.g. "OrgOne,OrgTwo"
# ADO_ORG:        legacy single-org fallback (used when ADO_ORGS is not set)
# ADO_PAT:        Personal Access Token — full access or scopes:
#                 Build (Read), Release (Read), Project and Team (Read), Agent Pools (Read)
#                 Generate at https://dev.azure.com/{org}/_usersSettings/tokens
# ADO_PROJECTS:   comma-separated project names (default: auto-discover per org)
ADO_PAT      = os.getenv("ADO_PAT", "")
ADO_ORG      = os.getenv("ADO_ORG", "")   # legacy single-org
_ado_orgs_raw = os.getenv("ADO_ORGS", "")
ADO_ORG_LIST: list[str] = (
    [o.strip() for o in _ado_orgs_raw.split(",") if o.strip()]
    or ([ADO_ORG] if ADO_ORG else [])
)
ADO_PROJECTS = [p.strip() for p in os.getenv("ADO_PROJECTS", "").split(",") if p.strip()]

# ── Mirantis / Prometheus (kubectl exec) ─────────────────────────────────────
KUBECTL_PATH        = os.getenv("KUBECTL_PATH", "kubectl")
KUBECTL_KUBECONFIG  = os.getenv("KUBECONFIG", "")
PROMETHEUS_POD      = os.getenv("PROMETHEUS_POD", "ucp-metrics")   # prefix or full name
PROMETHEUS_CONTAINER = "ucp-metrics-prometheus"
PROMETHEUS_NS       = "kube-system"
PROMETHEUS_URL      = "https://localhost:9090"
PROMETHEUS_CERT     = "/node_certs/cert.pem"
PROMETHEUS_KEY      = "/node_certs/key.pem"
PROMETHEUS_CA       = "/node_certs/ca.pem"

# Log Prometheus config at startup so it appears in docker logs
print(f"[prometheus] KUBECTL_PATH={KUBECTL_PATH}", flush=True)
print(f"[prometheus] KUBECONFIG={'SET → ' + KUBECTL_KUBECONFIG if KUBECTL_KUBECONFIG else 'NOT SET — live metrics disabled'}", flush=True)
print(f"[prometheus] PROMETHEUS_POD={PROMETHEUS_POD}", flush=True)
print(f"[grid] GRID_PROVIDER={GRID_PROVIDER}", flush=True)

# Maps dashboard app names → Kubernetes pod name prefix in your namespace.
# Set each value to the pod name prefix as shown by: kubectl get pods -n <namespace>
APP_POD_PATTERNS: dict[str, str] = {
    "CustomerSign":    "customersign-prod",
    "CustomerApp":     "customerapp-prod",
    "CustomerLeads":   "customerleads-prod",
    "CustomerService": "customerservice-prod",
    "CustomerTask":    "customertask-prod",
}
# Maps app names → Kubernetes deployment name (for live replica count).
# Set each value to the deployment name as shown by: kubectl get deployments -n <namespace>
APP_DEPLOYMENTS: dict[str, str] = {
    "CustomerSign":    "customersign-prod-deployment",
    "CustomerApp":     "customerapp-prod-deployment",
    "CustomerLeads":   "customerleads-prod-deployment",
    "CustomerService": "customerservice-prod-deployment",
    "CustomerTask":    "customertask-prod-deployment",
}
APP_NAMESPACE = "your-namespace"

# ── SCI constants (IF spec) ───────────────────────────────────────────────────
TEADS_X  = [0, 10, 50, 100]
TEADS_Y  = [0.12, 0.32, 0.75, 1.02]
NET_COEFF_KWH_PER_GB  = 0.001      # CCF
MEM_COEFF_KWH_PER_GB_HR = 0.000392 # CCF

# ── in-memory cache ───────────────────────────────────────────────────────────
_servers_cache = {}
_apps_cache = {}
_regions_cache = []
_network_cache = {}

# ── provider instances (built after data load so APP_POD_PATTERNS are ready) ──
_providers: Providers | None = None


def _get_providers() -> Providers:
    """Return the module-level Providers instance, building it on first call."""
    global _providers
    if _providers is None:
        _providers = build_providers(
            pod_patterns    = APP_POD_PATTERNS,
            app_deployments = APP_DEPLOYMENTS,
            app_namespace   = APP_NAMESPACE,
        )
    return _providers

# ══════════════════════════════════════════════════════════════════════════════
#  DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

def load_all_data():
    """Load servers, apps, regions, network on startup."""
    global _servers_cache, _apps_cache, _regions_cache, _network_cache
    
    print(f"Loading data from: {DATA_DIR}")
    print(f"Data directory exists: {DATA_DIR.exists()}")
    
    if not DATA_DIR.exists():
        print(f"ERROR: Data directory not found at {DATA_DIR}")
        print(f"Current working directory: {Path.cwd()}")
        print(f"__file__ location: {Path(__file__).parent}")
        return
    
    # ── servers ──
    print(f"Loading servers from {SERVERS_DIR}...")
    if not SERVERS_DIR.exists():
        print(f"WARNING: Servers directory not found")
    else:
        for f in SERVERS_DIR.glob("*.json"):
            with open(f) as fp:
                data = json.load(fp)
                # Cache by both instance_type AND filename (without .json)
                instance_type = data.get("instance_type") or data.get("name")
                filename_key = f.stem  # e.g., "aws-m5-2xlarge"
                
                _servers_cache[instance_type] = data
                if filename_key != instance_type:
                    _servers_cache[filename_key] = data  # Also cache by filename
                
                print(f"  Loaded server: {instance_type} (also as {filename_key})")
    
    # ── apps ──
    print(f"Loading apps from {APPS_DIR}...")
    if not APPS_DIR.exists():
        print(f"WARNING: Apps directory not found")
    else:
        for app_dir in APPS_DIR.iterdir():
            if not app_dir.is_dir():
                continue
            app_name = app_dir.name
            config_file = app_dir / "config.json"
            metrics_file = app_dir / "metrics-hourly.csv"
            
            if not config_file.exists():
                print(f"  Skipping {app_name} - no config.json")
                continue
            
            with open(config_file) as fp:
                config = json.load(fp)
            
            metrics = []
            if metrics_file.exists():
                with open(metrics_file) as fp:
                    reader = csv.DictReader(fp)
                    metrics = list(reader)
            
            _apps_cache[app_name] = {"config": config, "metrics": metrics}
            print(f"  Loaded app: {app_name} ({len(metrics)} hourly metrics)")
    
    # ── regions ──
    print(f"Loading regions from {REGIONS_FILE}...")
    if REGIONS_FILE.exists():
        with open(REGIONS_FILE) as fp:
            data = json.load(fp)
            _regions_cache = data.get("regions", [])
            print(f"  Loaded {len(_regions_cache)} regions")
    else:
        print(f"WARNING: Regions file not found")
    
    # ── network ──
    net_file = NETWORK_DIR / "common-network-devices.json"
    print(f"Loading network from {net_file}...")
    if net_file.exists():
        with open(net_file) as fp:
            _network_cache = json.load(fp)
            print(f"  Loaded network infrastructure data")
    else:
        print(f"WARNING: Network file not found")
    
    print(f"\n=== DATA LOAD SUMMARY ===")
    print(f"Servers: {len(_servers_cache)}")
    print(f"Apps: {len(_apps_cache)}")
    print(f"Regions: {len(_regions_cache)}")
    print(f"Network: {'loaded' if _network_cache else 'missing'}")
    print(f"=========================\n")


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _lerp(x: float, xs: list[float], ys: list[float]) -> float:
    x = max(xs[0], min(xs[-1], x))
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + t * (ys[i + 1] - ys[i])
    return ys[-1]


def _exec_prometheus_query(promql: str) -> dict | None:
    """Run a PromQL query via kubectl exec + curl inside the ucp-metrics pod. Returns parsed JSON or None."""
    try:
        result = subprocess.run(
            [KUBECTL_PATH, "--kubeconfig", KUBECTL_KUBECONFIG,
             "exec", "-n", PROMETHEUS_NS, PROMETHEUS_POD,
             "-c", PROMETHEUS_CONTAINER, "--",
             "curl", "-s", "--cert", PROMETHEUS_CERT,
             "--key", PROMETHEUS_KEY, "--cacert", PROMETHEUS_CA,
             f"{PROMETHEUS_URL}/api/v1/query", "--data-urlencode", f"query={promql}"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        data = json.loads(result.stdout)
        return data if data.get("status") == "success" and data.get("data", {}).get("result") else None
    except Exception:
        return None

# ══════════════════════════════════════════════════════════════════════════════
#  PROVIDER DELEGATION WRAPPERS
#  These thin functions keep existing call-sites in routes / diagnostics
#  working while delegating all real logic to the providers package.
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_grid(em_zone: str | None, fallback_gco2: float,
                watttime_region: str | None = None) -> dict:
    return _get_providers().grid.get_intensity(em_zone, watttime_region, fallback_gco2)


def get_live_metrics_for_app(app_name: str) -> dict | None:
    return _get_providers().metrics.get_metrics(app_name)


def _get_live_replica_count(app_name: str) -> int | None:
    return _get_providers().replicas.get_replica_count(app_name)


def _fetch_ga_views_per_hour(app_name: str) -> float | None:
    p = _get_providers()
    config = (_apps_cache.get(app_name) or {}).get("config", {})
    for fu in p.functional_units:
        if isinstance(fu, GA4Provider):
            return fu.get_units_per_hour(app_name, config)
    return None


def _fetch_ado_runs_per_hour() -> float | None:
    p = _get_providers()
    for fu in p.functional_units:
        if isinstance(fu, ADOProvider):
            return fu.get_units_per_hour("AzureDevOps", {})
    return None


def _fetch_ado_details() -> dict | None:
    p = _get_providers()
    for fu in p.functional_units:
        if isinstance(fu, ADOProvider):
            return fu.get_details()
    return None



# ══════════════════════════════════════════════════════════════════════════════
#  SCI CALCULATION
# ══════════════════════════════════════════════════════════════════════════════

def calculate_sci_for_app(app_name: str, duration_hours: float = 1.0, use_live_metrics: bool = False) -> dict:
    """
    Calculate SCI for one app using its config + current metrics.
    When use_live_metrics=True, fetches real-time CPU/memory/network from
    Mirantis Prometheus via kubectl exec, falling back to static config values.
    Returns: {sci, carbon_operational, carbon_embodied, energy, ...}
    """
    if app_name not in _apps_cache:
        raise ValueError(f"App {app_name} not found")

    app_data = _apps_cache[app_name]
    config = app_data["config"]
    metrics = app_data["metrics"]

    # ── live metrics override ─────────────────────────────────────────────────
    live = None
    if use_live_metrics:
        live = get_live_metrics_for_app(app_name)

    metrics_source = "prometheus-live" if live else "static-config"

    # ── extract config ────────────────────────────────────────────────────────
    server_type = config["server_config"]["server_type"]
    region_name = config["server_config"]["region"]

    # Live replica count from Kubernetes API (falls back to static config)
    live_replicas = _get_live_replica_count(app_name) if use_live_metrics else None
    server_count  = live_replicas if live_replicas is not None else config["server_config"]["count"]
    replicas_source = "kubernetes-live" if live_replicas is not None else "static-config"

    if server_type not in _servers_cache:
        raise ValueError(f"Server {server_type} not found")

    server = _servers_cache[server_type]

    # ── average usage (live overrides static when available) ──────────────────
    avg_cpu    = live["cpu_utilization_percent"]    if live else config["average_usage"]["cpu_utilization_percent"]
    avg_mem    = live["memory_utilization_percent"] if live else config["average_usage"]["memory_utilization_percent"]
    _net_gbps  = live["network_egress_gbps"]        if live else config["average_usage"].get("network_egress_gbps", 0)
    avg_net_gb = _net_gbps * duration_hours * 3600
    
    # ── server specs ──────────────────────────────────────────────────────────
    vcpus_alloc = server["specifications"]["vcpus"]
    vcpus_total = server["specifications"]["vcpus_total"]
    mem_gb = server["specifications"]["memory_gb"]
    tdp = server["specifications"]["cpu_tdp_watts"]
    pue = server["pue"]["value"]
    
    # ── embodied carbon ───────────────────────────────────────────────────────
    emb_total = server["embodied_carbon"]["allocated_share_gco2e"]
    lifespan_s = server["lifespan"]["seconds"]
    
    # ── grid intensity ────────────────────────────────────────────────────────
    region_info = next((r for r in _regions_cache if r["name"] == region_name), None)
    if not region_info:
        # fallback
        grid = {"intensity_gco2_kwh": 400, "source": "default", "region": region_name}
    else:
        grid = _fetch_grid(
                em_zone=region_info.get("electricity_maps_zone"),
                fallback_gco2=region_info["fallback_intensity_gco2_kwh"],
                watttime_region=region_info.get("watttime_region"),
            )
    
    intensity = grid["intensity_gco2_kwh"]
    
    # ══════════════════════════════════════════════════════════════════════════
    #  SCI PIPELINE
    # ══════════════════════════════════════════════════════════════════════════
    dur_s = duration_hours * 3600
    dur_h = duration_hours
    
    # 1. Teads interpolate
    cpu_factor = _lerp(avg_cpu, TEADS_X, TEADS_Y)
    
    # 2-6. CPU energy
    cpu_wattage = cpu_factor * tdp
    watt_dur = cpu_wattage * dur_s
    cpu_raw_kwh = watt_dur / 3_600_000.0
    vcpu_ratio = vcpus_total / max(vcpus_alloc, 1)
    cpu_energy = cpu_raw_kwh / vcpu_ratio
    
    # 7. Memory energy
    mem_energy = mem_gb * (avg_mem / 100.0) * MEM_COEFF_KWH_PER_GB_HR * dur_h
    
    # 8. Network energy
    net_energy = avg_net_gb * NET_COEFF_KWH_PER_GB
    
    # 9. Sum energy
    it_energy = cpu_energy + mem_energy + net_energy
    
    # 10. PUE
    total_energy = it_energy * pue
    
    # 12. Operational carbon
    carbon_op = total_energy * intensity
    
    # 13. Embodied carbon
    time_ratio = dur_s / max(lifespan_s, 1)
    carbon_emb = emb_total * time_ratio
    
    # 14. Total carbon
    carbon = carbon_op + carbon_emb
    
    # 15. SCI — use live functional unit count when available
    #     GA4 for web apps; ADO Builds API for the CI/CD pipeline app
    ga_views_per_hour = _fetch_ga_views_per_hour(app_name) if use_live_metrics else None
    ado_runs_per_hour = (
        _fetch_ado_runs_per_hour()
        if use_live_metrics and app_name == "AzureDevOps"
        else None
    )

    if ado_runs_per_hour is not None:
        fu_count = ado_runs_per_hour * duration_hours
        fu_source = "azure-devops-live"
    elif ga_views_per_hour is not None:
        fu_count = ga_views_per_hour * duration_hours
        fu_source = "google-analytics-live"
    else:
        fu_count = config["functional_unit"].get("average_per_hour", 1000) * duration_hours
        fu_source = "config-estimate"
    sci = carbon / max(fu_count, 1)
    
    # ── scale by server count ─────────────────────────────────────────────────
    carbon_total = carbon * server_count
    carbon_op_total = carbon_op * server_count
    carbon_emb_total = carbon_emb * server_count
    energy_total = total_energy * server_count
    
    # ── cost estimate ─────────────────────────────────────────────────────────
    cost_per_hr = server.get("cost_per_hour_usd")
    if cost_per_hr:
        cost_total = cost_per_hr * server_count * duration_hours
    else:
        cost_total = None
    
    return {
        "app_name": app_name,
        "sci": round(sci, 8),
        "functional_unit": config["functional_unit"]["type"],
        "functional_unit_count": fu_count,
        "functional_unit_source": fu_source,
        "carbon_gco2e": round(carbon_total, 4),
        "carbon_operational_gco2e": round(carbon_op_total, 4),
        "carbon_embodied_gco2e": round(carbon_emb_total, 4),
        "total_energy_kwh": round(energy_total, 6),
        "grid_intensity_gco2_kwh": intensity,
        "grid_source": grid["source"],
        "region": region_name,
        "server_type": server_type,
        "server_count": server_count,
        "cost_usd": round(cost_total, 2) if cost_total else None,
        "metrics_source": metrics_source,
        "replicas_source": replicas_source,
        "cpu_utilization_percent": avg_cpu,
        "memory_utilization_percent": avg_mem,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  OPTIMIZATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def generate_optimization_recommendations(app_name: str, current_sci: dict) -> list[dict]:
    """
    Generate recommendations:
      1. Move to different region (lower carbon intensity)
      2. Change server type (right-sizing)
      3. Time-shift batch workloads
    """
    recommendations = []
    
    app_data = _apps_cache[app_name]
    config = app_data["config"]
    current_region = config["server_config"]["region"]
    current_server = config["server_config"]["server_type"]
    current_carbon = current_sci["carbon_gco2e"]
    current_cost = current_sci.get("cost_usd")
    
    # ────────────────────────────────────────────────────────────────────────
    #  1. REGION RELOCATION
    # ────────────────────────────────────────────────────────────────────────
    for region in _regions_cache:
        if region["name"] == current_region:
            continue
        
        # check if server type is available in this region
        server_obj = _servers_cache.get(current_server)
        if not server_obj:
            continue
        
        avail_regions = server_obj.get("regions_available", [])
        if region["name"] not in avail_regions:
            continue
        
        # estimate carbon with this region's intensity
        new_intensity = region["fallback_intensity_gco2_kwh"]
        old_intensity = current_sci["grid_intensity_gco2_kwh"]
        
        if new_intensity >= old_intensity:
            continue  # no improvement
        
        # recalculate operational carbon
        energy = current_sci["total_energy_kwh"]
        new_carbon_op = energy * new_intensity
        new_carbon_total = new_carbon_op + current_sci["carbon_embodied_gco2e"]
        
        carbon_reduction_pct = ((current_carbon - new_carbon_total) / current_carbon) * 100
        
        if carbon_reduction_pct < 5:  # threshold
            continue
        
        recommendations.append({
            "type": "region_relocation",
            "priority": "high" if carbon_reduction_pct > 20 else "medium",
            "title": f"Move to {region['location']}",
            "current_region": current_region,
            "recommended_region": region["name"],
            "carbon_reduction_gco2e": round(current_carbon - new_carbon_total, 2),
            "carbon_reduction_percent": round(carbon_reduction_pct, 1),
            "new_grid_intensity": new_intensity,
            "renewable_percent": region["renewable_percent"],
            "estimated_cost_impact": "neutral" if not current_cost else "variable",
            "notes": region.get("notes", ""),
        })
    
    # ────────────────────────────────────────────────────────────────────────
    #  2. SERVER RIGHT-SIZING
    # ────────────────────────────────────────────────────────────────────────
    current_cpu = config["average_usage"]["cpu_utilization_percent"]
    
    # if CPU < 40%, recommend downsize
    if current_cpu < 40:
        # find smaller server from same provider
        provider = _servers_cache[current_server]["provider"]
        for server_name, server_obj in _servers_cache.items():
            if server_obj["provider"] != provider:
                continue
            if server_name == current_server:
                continue
            
            # check if smaller
            if server_obj["specifications"]["vcpus"] >= _servers_cache[current_server]["specifications"]["vcpus"]:
                continue
            
            # rough estimate: proportional carbon reduction
            vcpu_ratio = server_obj["specifications"]["vcpus"] / _servers_cache[current_server]["specifications"]["vcpus"]
            estimated_carbon = current_carbon * vcpu_ratio * 0.85  # assume 15% efficiency gain
            
            carbon_reduction = current_carbon - estimated_carbon
            carbon_reduction_pct = (carbon_reduction / current_carbon) * 100
            
            if carbon_reduction_pct < 10:
                continue
            
            cost_ratio = 1.0
            if current_cost and server_obj.get("cost_per_hour_usd"):
                cost_ratio = server_obj["cost_per_hour_usd"] / _servers_cache[current_server]["cost_per_hour_usd"]
            
            cost_reduction_pct = (1 - cost_ratio) * 100
            
            recommendations.append({
                "type": "server_rightsizing",
                "priority": "medium",
                "title": f"Downsize to {server_obj['name']}",
                "current_server": current_server,
                "recommended_server": server_name,
                "carbon_reduction_gco2e": round(carbon_reduction, 2),
                "carbon_reduction_percent": round(carbon_reduction_pct, 1),
                "cost_reduction_percent": round(cost_reduction_pct, 1) if current_cost else None,
                "cpu_utilization_current": current_cpu,
                "notes": "Low CPU utilization indicates over-provisioning",
            })
            break  # only recommend one downsize

    # ────────────────────────────────────────────────────────────────────────
    #  2b. REPLICA SCALE-DOWN
    #  When live CPU < 10% and more than 1 replica is running, the extra pods
    #  are burning embodied + operational carbon with no real benefit.
    # ────────────────────────────────────────────────────────────────────────
    current_replicas = current_sci.get("server_count", 1)
    cpu_live         = current_sci.get("cpu_utilization_percent", 100)
    metrics_are_live = current_sci.get("replicas_source") == "kubernetes-live"

    if current_replicas > 1 and cpu_live < 10 and metrics_are_live:
        # Scale to 1 when near-idle (<2%), otherwise proportional minimum
        if cpu_live < 2:
            recommended_replicas = 1
        else:
            # keep enough replicas to handle 30% headroom at realistic load
            recommended_replicas = max(1, round(current_replicas * (cpu_live / 30)))
            recommended_replicas = min(recommended_replicas, current_replicas - 1)

        carbon_per_replica = current_carbon / current_replicas
        new_carbon         = carbon_per_replica * recommended_replicas
        carbon_reduction   = current_carbon - new_carbon
        carbon_reduction_pct = (carbon_reduction / current_carbon) * 100

        deployment = APP_DEPLOYMENTS.get(app_name, f"{app_name.lower()}-deployment")
        kubectl_cmd = (
            f"kubectl scale deployment {deployment} "
            f"--replicas={recommended_replicas} -n {APP_NAMESPACE}"
        )

        recommendations.append({
            "type": "replica_scaledown",
            "priority": "high",
            "title": f"Scale down: {current_replicas} → {recommended_replicas} replica{'s' if recommended_replicas != 1 else ''}",
            "current_replicas": current_replicas,
            "recommended_replicas": recommended_replicas,
            "carbon_reduction_gco2e": round(carbon_reduction, 2),
            "carbon_reduction_percent": round(carbon_reduction_pct, 1),
            "cpu_utilization_current": cpu_live,
            "kubectl_command": kubectl_cmd,
            "notes": (
                f"CPU is {cpu_live:.1f}% across {current_replicas} replicas — "
                f"well below the threshold to justify this count. "
                f"Scaling to {recommended_replicas} saves proportional embodied + operational carbon."
            ),
        })
    
    # ────────────────────────────────────────────────────────────────────────
    #  3. CLOUD MIGRATION — On-Premises → Azure South Central US
    #  Models the carbon impact of lifting workloads from the on-prem TX
    #  datacenter into Azure southcentralus (same ERCOT grid, better PUE).
    # ────────────────────────────────────────────────────────────────────────
    current_server_obj = _servers_cache.get(current_server, {})
    if current_server_obj.get("provider") == "On-Premises":
        azure_server_key = "azure-d4s-v3"
        azure_server = _servers_cache.get(azure_server_key)
        azure_region_name = "southcentralus"
        azure_region = next((r for r in _regions_cache if r["name"] == azure_region_name), None)

        if azure_server and azure_region:
            old_pue = current_server_obj["pue"]["value"]          # e.g. 1.58
            new_pue = azure_server["pue"]["value"]                 # 1.18
            old_intensity = current_sci["grid_intensity_gco2_kwh"]
            azure_intensity = azure_region["fallback_intensity_gco2_kwh"]

            # Strip PUE from total_energy to get raw IT energy, then re-apply Azure PUE.
            # total_energy_kwh = it_energy * pue * server_count
            total_energy = current_sci["total_energy_kwh"]
            server_count = current_sci.get("server_count", 1)
            it_energy_total = total_energy / old_pue          # remove on-prem PUE
            new_total_energy = it_energy_total * new_pue       # apply Azure PUE

            # New operational carbon (same grid zone, better PUE)
            new_carbon_op_total = new_total_energy * azure_intensity

            # New embodied carbon over 1-hour slice (Azure VM amortised share)
            dur_s = 3600
            azure_lifespan_s = azure_server["lifespan"]["seconds"]
            azure_emb = azure_server["embodied_carbon"]["allocated_share_gco2e"]
            new_carbon_emb_total = (azure_emb * (dur_s / azure_lifespan_s)) * server_count

            new_carbon_total = new_carbon_op_total + new_carbon_emb_total
            carbon_reduction = current_carbon - new_carbon_total
            carbon_reduction_pct = (carbon_reduction / current_carbon) * 100 if current_carbon else 0

            pue_saving_pct = round((1 - new_pue / old_pue) * 100, 1)
            cost_per_hr = (azure_server.get("cost_per_hour_usd") or 0.192) * server_count

            if carbon_reduction_pct >= 5:
                recommendations.append({
                    "type": "cloud_migration",
                    "priority": "high" if carbon_reduction_pct > 15 else "medium",
                    "title": "Migrate to Azure South Central US (San Antonio, TX)",
                    "current_server": current_server,
                    "current_region": current_region,
                    "recommended_server": azure_server_key,
                    "recommended_region": azure_region_name,
                    "recommended_region_location": azure_region["location"],
                    "carbon_reduction_gco2e": round(carbon_reduction, 2),
                    "carbon_reduction_percent": round(carbon_reduction_pct, 1),
                    "new_carbon_gco2e": round(new_carbon_total, 4),
                    "pue_current": old_pue,
                    "pue_azure": new_pue,
                    "pue_saving_percent": pue_saving_pct,
                    "grid_intensity_gco2_kwh": azure_intensity,
                    "renewable_percent": azure_region["renewable_percent"],
                    "estimated_cost_per_hour_usd": round(cost_per_hr, 4),
                    "cost_model": "OpEx (pay-per-use) vs CapEx (owned hardware)",
                    "notes": (
                        f"Azure South Central US uses the same ERCOT grid as your on-prem TX datacenter "
                        f"(~{azure_intensity} gCO₂/kWh), so no carbon penalty for staying in Texas. "
                        f"The gain is purely from PUE: Azure {new_pue} vs on-prem {old_pue} "
                        f"= {pue_saving_pct}% less energy overhead. "
                        f"Embodied carbon shifts from full hardware ownership to a shared VM allocation."
                    ),
                })

    # ────────────────────────────────────────────────────────────────────────
    #  4. TIME-SHIFTING (for batch workloads)
    # ────────────────────────────────────────────────────────────────────────
    if "batch" in config.get("workload_pattern", {}).get("type", "").lower():
        region_info = next((r for r in _regions_cache if r["name"] == current_region), None)
        if region_info and region_info.get("typical_best_hours"):
            recommendations.append({
                "type": "time_shifting",
                "priority": "low",
                "title": "Schedule batch jobs during low-carbon hours",
                "current_region": current_region,
                "best_hours": region_info["typical_best_hours"],
                "carbon_reduction_percent": 15,  # typical estimate
                "notes": "Grid carbon intensity varies throughout the day",
            })
    
    # ── sort by carbon reduction ──
    recommendations.sort(key=lambda x: x.get("carbon_reduction_percent", 0), reverse=True)
    
    return recommendations


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "ts": datetime.now(timezone.utc).isoformat()})


@app.route("/api/debug")
def debug():
    """Debug endpoint to check data loading status."""
    return jsonify({
        "data_dir": str(DATA_DIR),
        "data_dir_exists": DATA_DIR.exists(),
        "servers_loaded": len(_servers_cache),
        "apps_loaded": len(_apps_cache),
        "regions_loaded": len(_regions_cache),
        "network_loaded": bool(_network_cache),
        "servers_list": list(_servers_cache.keys()),
        "apps_list": list(_apps_cache.keys()),
        "cwd": str(Path.cwd()),
        "file_location": str(Path(__file__).parent),
    })


@app.route("/api/apps")
def list_apps():
    """Return list of all applications with basic info."""
    apps = []
    for app_name, app_data in _apps_cache.items():
        config = app_data["config"]
        apps.append({
            "app_name": app_name,
            "description": config.get("description", ""),
            "server_type": config["server_config"]["server_type"],
            "server_count": config["server_config"]["count"],
            "region": config["server_config"]["region"],
            "functional_unit": config["functional_unit"]["type"],
        })
    return jsonify({"apps": apps})


@app.route("/api/servers")
def list_servers():
    """Return all server configurations."""
    servers = []
    for name, server in _servers_cache.items():
        servers.append({
            "name": name,
            "provider": server.get("provider"),
            "vcpus": server["specifications"]["vcpus"],
            "memory_gb": server["specifications"]["memory_gb"],
            "cpu_tdp_watts": server["specifications"]["cpu_tdp_watts"],
            "embodied_gco2e": server["embodied_carbon"]["allocated_share_gco2e"],
            "pue": server["pue"]["value"],
            "cost_per_hour_usd": server.get("cost_per_hour_usd"),
        })
    return jsonify({"servers": servers})


@app.route("/api/regions")
def list_regions():
    """Return all regions with carbon intensity."""
    return jsonify({"regions": _regions_cache})


@app.route("/api/sci/<app_name>")
def get_sci(app_name: str):
    """Calculate SCI for a single app. Add ?live=true to use real-time Mirantis metrics."""
    try:
        use_live = request.args.get("live", "false").lower() == "true"
        result = calculate_sci_for_app(app_name, use_live_metrics=use_live)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/live-metrics/<app_name>")
def get_live_metrics(app_name: str):
    """Return current CPU/memory/network from Mirantis Prometheus for one app."""
    if app_name not in _apps_cache:
        return jsonify({"error": f"App {app_name} not found"}), 404

    # Diagnostics
    kc = bool(KUBECTL_KUBECONFIG)
    in_map = app_name in APP_POD_PATTERNS

    if not kc:
        return jsonify({
            "app_name": app_name, "available": False,
            "reason": "KUBECONFIG env var is not set",
            "kubeconfig_set": False,
        })
    if not in_map:
        return jsonify({
            "app_name": app_name, "available": False,
            "reason": f"{app_name} has no pod pattern configured in APP_POD_PATTERNS",
            "kubeconfig_set": True,
        })

    # Run a quick connectivity test
    test = _exec_prometheus_query("up{job='ucp'}")
    if not test:
        # Try to get raw error by running kubectl directly
        try:
            result = subprocess.run(
                [KUBECTL_PATH, "--kubeconfig", KUBECTL_KUBECONFIG,
                 "exec", "-n", PROMETHEUS_NS, PROMETHEUS_POD,
                 "-c", PROMETHEUS_CONTAINER, "--",
                 "curl", "-s", "--cert", PROMETHEUS_CERT,
                 "--key", PROMETHEUS_KEY, "--cacert", PROMETHEUS_CA,
                 f"{PROMETHEUS_URL}/-/healthy"],
                capture_output=True, text=True, timeout=15
            )
            return jsonify({
                "app_name": app_name, "available": False,
                "reason": "Prometheus query returned no data",
                "kubeconfig_set": True,
                "kubectl_exit_code": result.returncode,
                "kubectl_stdout": result.stdout[:300],
                "kubectl_stderr": result.stderr[:300],
            })
        except Exception as e:
            return jsonify({
                "app_name": app_name, "available": False,
                "reason": "kubectl exec failed",
                "kubeconfig_set": True,
                "error": str(e),
            })

    live = get_live_metrics_for_app(app_name)
    if live is None:
        return jsonify({
            "app_name": app_name, "available": False,
            "reason": "Prometheus reachable but no container metrics found for pod pattern",
            "pod_pattern": APP_POD_PATTERNS[app_name],
            "namespace": APP_NAMESPACE,
        })
    return jsonify({"app_name": app_name, "available": True, **live})


@app.route("/api/sci/all")
def get_all_sci():
    """Calculate SCI for all apps and rank them. Add ?live=true for real-time Mirantis metrics."""
    try:
        use_live = request.args.get("live", "false").lower() == "true"
        results = []
        for app_name in _apps_cache.keys():
            sci_data = calculate_sci_for_app(app_name, use_live_metrics=use_live)
            results.append(sci_data)
        
        # sort by SCI score
        results.sort(key=lambda x: x["sci"])
        
        return jsonify({"applications": results})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommendations/<app_name>")
def get_recommendations(app_name: str):
    """Get optimization recommendations for an app."""
    try:
        current_sci = calculate_sci_for_app(app_name)
        recs = generate_optimization_recommendations(app_name, current_sci)
        return jsonify({
            "app_name": app_name,
            "current_sci": current_sci,
            "recommendations": recs,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


LANGUAGE_OPTIMIZER_URL = os.environ.get("LANGUAGE_OPTIMIZER_URL", "http://localhost:8000")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


@app.route("/api/language-optimize", methods=["POST"])
def language_optimize():
    """Proxy to the Language Optimizer service to analyze code for energy efficiency."""
    try:
        payload = request.get_json(force=True)
        if not payload or "code" not in payload or "filename" not in payload:
            return jsonify({"error": "Missing required fields: code, filename"}), 400

        resp = http.post(
            f"{LANGUAGE_OPTIMIZER_URL}/api/analyze",
            json=payload,
            timeout=120,
        )
        return Response(resp.content, status=resp.status_code, content_type="application/json")
    except http.exceptions.ConnectionError:
        return jsonify({"error": "Language Optimizer service is unavailable"}), 503
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/ado/details")
def get_ado_details():
    """
    Return Azure DevOps agent pool status and 28-day build/release breakdown.
    Always returns 200 with a structured body so the frontend can display the
    real reason for any failure instead of a generic error message.
    Returns ok=False reason=loading while the background pre-warm is still running.
    """
    try:
        if not ADO_ORG_LIST or not ADO_PAT:
            return jsonify({
                "ok": False,
                "reason": "credentials_missing",
                "message": "ADO_ORGS and ADO_PAT are not set in the container environment. "
                           "Check that .env is present next to docker-compose.yml and rebuild the container.",
            })

        # If the background pre-warm hasn't finished yet, return immediately
        # so nginx doesn't time out. The frontend will retry.
        if not _prewarm_done:
            return jsonify({
                "ok": False,
                "reason": "loading",
                "message": "ADO data is being fetched in the background. Please wait a moment and try again.",
                "retry_after": 8,
            })

        details = _fetch_ado_details()
        if details is None:
            return jsonify({
                "ok": False,
                "reason": "api_error",
                "message": "ADO API call succeeded but returned no data. "
                           "Check that the PAT has Build/Release/Project read scopes and has not expired.",
            })

        # Attach per-agent carbon estimate from current SCI calculation
        try:
            sci = calculate_sci_for_app("AzureDevOps")
            agent_count = sci.get("server_count", 1)
            details["carbon_per_agent_gco2e"] = round(sci["carbon_gco2e"] / max(agent_count, 1), 4)
            details["total_carbon_gco2e"] = sci["carbon_gco2e"]
            details["grid_intensity_gco2_kwh"] = sci["grid_intensity_gco2_kwh"]
        except Exception:
            pass

        details["ok"] = True
        return jsonify(details)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "reason": "exception", "message": str(e)})


@app.route("/api/compare")
def compare_all():
    """
    Full comparison endpoint:
      - SCI for all apps
      - Recommendations for each
      - Regional carbon intensity comparison
    Accepts ?live=true to use Prometheus live metrics.
    """
    use_live = request.args.get("live", "false").lower() == "true"
    try:
        app_names = list(_apps_cache.keys())

        def _calc_one(name):
            sci = calculate_sci_for_app(name, use_live_metrics=use_live)
            recs = generate_optimization_recommendations(name, sci)
            return {"app": sci, "recommendations": recs}

        results = []
        with ThreadPoolExecutor(max_workers=len(app_names)) as ex:
            futures = {ex.submit(_calc_one, n): n for n in app_names}
            for fut in as_completed(futures):
                try:
                    results.append(fut.result())
                except Exception as exc:
                    print(f"[compare] {futures[fut]} failed: {exc}", flush=True)
        
        # regional carbon intensity snapshot
        region_intensities = []
        for region in _regions_cache:
            grid = _fetch_grid(
                    em_zone=region.get("electricity_maps_zone"),
                    fallback_gco2=region["fallback_intensity_gco2_kwh"],
                    watttime_region=region.get("watttime_region"),
                )
            region_intensities.append({
                "name": region["name"],
                "location": region["location"],
                "intensity_gco2_kwh": grid["intensity_gco2_kwh"],
                "source": grid["source"],
                "renewable_percent": region["renewable_percent"],
            })
        
        return jsonify({
            "applications": results,
            "regions": region_intensities,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
#  STARTUP
# ══════════════════════════════════════════════════════════════════════════════

# Load data at module import time (works with both Flask dev server and Gunicorn)
print("\n" + "="*60)
print("  Enterprise SCI Platform - Backend Loading Data")
print("="*60)
print(f"Current working directory: {Path.cwd()}")
print(f"Script location: {Path(__file__).parent}")
print(f"Expected data directory: {DATA_DIR}")
print(f"Data directory exists: {DATA_DIR.exists()}")

if DATA_DIR.exists():
    print(f"\nContents of {DATA_DIR}:")
    try:
        for item in DATA_DIR.iterdir():
            print(f"  - {item.name}")
    except Exception as e:
        print(f"  Error listing: {e}")
else:
    print(f"\n⚠️  WARNING: Data directory not found!")
    print(f"   Looking for: {DATA_DIR}")
    print(f"   Make sure Docker volume is mounted correctly")

print("\nLoading data files...")
load_all_data()
print("="*60 + "\n")

# Pre-warm slow caches in the background so the first live-mode request
# responds immediately instead of waiting 30-60 s for cold ADO + GA4 data.
import threading as _threading

_prewarm_done = False

def _prewarm_live_caches():
    global _prewarm_done
    try:
        print("[startup] pre-warming ADO + GA4 caches...", flush=True)
        _fetch_ado_runs_per_hour()
        _fetch_ado_details()
        for _name in list(_apps_cache.keys()):
            _fetch_ga_views_per_hour(_name)
        print("[startup] cache pre-warm complete", flush=True)
    except Exception as _exc:
        print(f"[startup] cache pre-warm error: {_exc}", flush=True)
    finally:
        _prewarm_done = True

_threading.Thread(target=_prewarm_live_caches, daemon=True).start()

if __name__ == "__main__":
    print(f"Starting Flask development server on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
