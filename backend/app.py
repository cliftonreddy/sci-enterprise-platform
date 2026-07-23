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

import json, os, time, csv, traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from collections import defaultdict

from flask import Flask, Response, jsonify, request
from flask_cors import CORS
import requests as http

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


def _wt_login() -> str | None:
    global _WT_TOKEN, _WT_TOKEN_TS
    if _WT_TOKEN and (time.time() - _WT_TOKEN_TS) < _WT_TOKEN_TTL:
        return _WT_TOKEN
    if not WT_USER or not WT_PASS:
        return None
    try:
        r = http.get(f"{WT_BASE}/v3/login",
                     params={"username": WT_USER, "password": WT_PASS},
                     timeout=8)
        r.raise_for_status()
        _WT_TOKEN = r.json().get("token")
        _WT_TOKEN_TS = time.time()
        return _WT_TOKEN
    except Exception:
        return None


def _fetch_grid(watttime_region: str | None, fallback_gco2: float) -> dict:
    """WattTime v3 or fallback."""
    if not watttime_region:
        return {
            "intensity_gco2_kwh": fallback_gco2,
            "source": "static-fallback",
            "region": watttime_region or "unknown",
        }
    
    token = _wt_login()
    if token:
        try:
            r = http.get(f"{WT_BASE}/v3/forecast",
                         headers={"Authorization": f"Bearer {token}"},
                         params={"region": watttime_region, "signal_type": "co2_moer"},
                         timeout=8)
            r.raise_for_status()
            data = r.json().get("data", [])
            if data:
                moer = data[0]["value"]
                g_kwh = moer * 0.453592 / 1000.0
                return {
                    "intensity_gco2_kwh": round(g_kwh, 2),
                    "source": "watttime-v3",
                    "region": watttime_region,
                    "moer_raw_lb_mwh": moer,
                }
        except Exception:
            pass
    
    return {
        "intensity_gco2_kwh": fallback_gco2,
        "source": "static-fallback",
        "region": watttime_region,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  SCI CALCULATION
# ══════════════════════════════════════════════════════════════════════════════

def calculate_sci_for_app(app_name: str, duration_hours: float = 1.0) -> dict:
    """
    Calculate SCI for one app using its config + current metrics.
    Returns: {sci, carbon_operational, carbon_embodied, energy, ...}
    """
    if app_name not in _apps_cache:
        raise ValueError(f"App {app_name} not found")
    
    app_data = _apps_cache[app_name]
    config = app_data["config"]
    metrics = app_data["metrics"]
    
    # ── extract config ────────────────────────────────────────────────────────
    server_type = config["server_config"]["server_type"]
    server_count = config["server_config"]["count"]
    region_name = config["server_config"]["region"]
    
    if server_type not in _servers_cache:
        raise ValueError(f"Server {server_type} not found")
    
    server = _servers_cache[server_type]
    
    # ── average usage ─────────────────────────────────────────────────────────
    avg_cpu = config["average_usage"]["cpu_utilization_percent"]
    avg_mem = config["average_usage"]["memory_utilization_percent"]
    avg_net_gb = config["average_usage"].get("network_egress_gbps", 0) * duration_hours * 3600
    
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
        grid = _fetch_grid(region_info.get("watttime_region"),
                           region_info["fallback_intensity_gco2_kwh"])
    
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
    
    # 15. SCI
    fu_count = config["functional_unit"].get("average_per_hour", 1000) * duration_hours
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
    #  3. TIME-SHIFTING (for batch workloads)
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
    """Calculate SCI for a single app."""
    try:
        result = calculate_sci_for_app(app_name)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/sci/all")
def get_all_sci():
    """Calculate SCI for all apps and rank them."""
    try:
        results = []
        for app_name in _apps_cache.keys():
            sci_data = calculate_sci_for_app(app_name)
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


@app.route("/api/compare")
def compare_all():
    """
    Full comparison endpoint:
      - SCI for all apps
      - Recommendations for each
      - Regional carbon intensity comparison
    """
    try:
        results = []
        for app_name in _apps_cache.keys():
            sci_data = calculate_sci_for_app(app_name)
            recs = generate_optimization_recommendations(app_name, sci_data)
            results.append({
                "app": sci_data,
                "recommendations": recs,
            })
        
        # regional carbon intensity snapshot
        region_intensities = []
        for region in _regions_cache:
            grid = _fetch_grid(region.get("watttime_region"),
                               region["fallback_intensity_gco2_kwh"])
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

if __name__ == "__main__":
    print(f"Starting Flask development server on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
