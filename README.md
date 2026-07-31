# Enterprise Multi-Application SCI Platform

A comprehensive carbon intensity comparison platform for enterprise applications. Compare SCI scores across 6 applications (AzureDevOps, CustomerApp, CustomerLeads, CustomerService, CustomerSign, CustomerTask), get optimization recommendations for hardware and region selection, and visualize carbon impact across your infrastructure.

---

## Features

### ✅ Multi-Application SCI Calculation
- Real hardware configurations (AWS m5.2xlarge, c5.4xlarge, Azure D4s v3, GCP n2-standard-4, Dell R740)
- Actual embodied carbon data from Boavizta API and Cloud Carbon Footprint
- Hourly usage metrics with realistic workload patterns
- Full Impact Framework SCI pipeline (16 stages)

### ✅ Optimization Engine
Three types of recommendations:
1. **Region Relocation** - Move to lower-carbon regions (live WattTime data)
2. **Server Right-Sizing** - Downsize over-provisioned instances
3. **Time-Shifting** - Schedule batch jobs during low-carbon hours

### ✅ Live Carbon Intensity
- WattTime v3 API integration for real-time grid data
- Multi-region comparison (US, EU, APAC)
- Fallback to IEA 2022 static intensities

### ✅ Enterprise Dashboard
- Side-by-side app comparison with ranking
- Drill-down per application
- Carbon breakdown (Operational vs Embodied)
- Regional intensity heatmap
- Cost estimates alongside carbon

---

## Application Portfolio

| Application | Server Config | Region | Workload Pattern | Functional Unit |
|-------------|---------------|--------|------------------|-----------------|
| **AzureDevOps**    | 11× vSphere build node  | on-premises-datacenter | Burst (business hours CI/CD) | pipeline_run |
| **CustomerApp**    | 1× vSphere worker node  | on-premises-datacenter | Steady-state (business hours) | page_view |
| **CustomerLeads**  | 1× vSphere worker node  | on-premises-datacenter | Steady-state (business hours) | api_request |
| **CustomerService**| 1× vSphere worker node  | on-premises-datacenter | Steady-state (business hours) | page_view |
| **CustomerSign**   | 1× vSphere worker node  | on-premises-datacenter | Steady-state (business hours) | page_view |
| **CustomerTask**   | 1× vSphere worker node  | on-premises-datacenter | Steady-state (business hours) | api_request |

---

## Server Hardware Specifications

### AWS m5.2xlarge (General Purpose)
- **vCPUs:** 8 / 96 total
- **Memory:** 32 GB / 384 GB total
- **CPU:** Intel Xeon Platinum 8175M (205W TDP)
- **Embodied Carbon:** 100,400 gCO₂eq (allocated share)
- **PUE:** 1.15
- **Cost:** $0.384/hour

### AWS c5.4xlarge (Compute Optimized)
- **vCPUs:** 16 / 96 total
- **Memory:** 32 GB / 192 GB total
- **CPU:** Intel Xeon Platinum 8124M (240W TDP)
- **Embodied Carbon:** 225,000 gCO₂eq
- **PUE:** 1.15
- **Cost:** $0.68/hour

### Azure Standard_D4s_v3
- **vCPUs:** 4 / 64 total
- **Memory:** 16 GB / 256 GB total
- **CPU:** Intel Xeon E5-2673 v4 (135W TDP)
- **Embodied Carbon:** 59,200 gCO₂eq
- **PUE:** 1.18
- **Cost:** $0.192/hour

### GCP n2-standard-4
- **vCPUs:** 4 / 80 total
- **Memory:** 16 GB / 320 GB total
- **CPU:** Intel Xeon Cascade Lake (165W TDP)
- **Embodied Carbon:** 55,000 gCO₂eq
- **PUE:** 1.10 (best-in-class)
- **Cost:** $0.195/hour

### Dell PowerEdge R740 (On-Premises)
- **vCPUs:** 32 (dedicated)
- **Memory:** 128 GB (dedicated)
- **CPU:** 2× Intel Xeon Gold 6130 (250W TDP)
- **Embodied Carbon:** 365,100 gCO₂eq (full server)
- **PUE:** 1.58 (typical enterprise DC)
- **Cost:** CapEx model ($8,500 upfront)

---

## Embodied Carbon Breakdown

All values from **Boavizta API** and **Cloud Carbon Footprint** methodology:

| Component | gCO₂eq | Source |
|-----------|--------|--------|
| CPU (Intel Xeon) | 72,000 - 95,000 | Boavizta API |
| Memory (DDR4 ECC, per GB) | 12.5 | CCF |
| Storage (SSD) | 5,000 - 8,000 | CCF |
| Motherboard/Chipset | 65,000 - 78,000 | CCF baseline |
| Network Card | 12,000 - 22,000 | CCF |
| Power Supply | 18,000 | Dell hardware |
| Cooling Fans | 3,500 | Server cooling |

**Network Infrastructure** (shared across apps):
- Datacenter switches: 3,400,000 gCO₂eq
- Routers: 500,000 gCO₂eq
- Load balancers: 360,000 gCO₂eq
- Allocation: 0.15 gCO₂eq per GB transferred

---

## Quick Start

### Prerequisites
- Docker ≥ 20.10
- Docker Compose v2

### 1. Clone and Configure
```bash
cd sci-carbon-dashboard
cp .env.example .env
# Optional: Add WattTime credentials for live data
```

### 2. Launch
```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API | http://localhost:5000 |

### 3. Explore
- View all 6 applications ranked by SCI
- Click any app to see detailed breakdown
- Review optimization recommendations
- Compare regional carbon intensities

---

## Credential Files

The dashboard runs fully with static fallback data — **no credentials are required to start it**. Each integration below degrades gracefully when its credential file or keys are absent:

| Missing credential | Fallback behaviour |
|---|---|
| `ELECTRICITY_MAPS_TOKEN` / `WATTTIME_*` | Grid intensity uses static IEA 2022 values from `grid-regions.json` |
| `ga4-service-account.json` / `GA4_PROPERTY_ID` | Functional units use static hourly estimates from each app's `config.json` |
| `ADO_PAT` / `ADO_ORGS` | Build counts use static estimates; live ADO endpoints return a "not configured" message |
| `ucp-bundle` / `KUBECONFIG_DIR` | Prometheus metrics disabled; replica counts and CPU utilisation use static `config.json` values |

The only hard requirement is that **`.env` must exist** (even if all values are blank) because Docker Compose reads it at startup. Running `cp .env.example .env` is sufficient.

The sections below explain each file only if you want to enable the corresponding live data source. None of these files should ever be committed — they are all covered by `.gitignore`.

### 1. `.env` — API keys and connection settings
**Location:** `sci-carbon-dashboard/.env`
**Template:** copy from `sci-carbon-dashboard/.env.example`

Required to connect to any external service:

| What you're enabling | Keys to populate |
|---|---|
| **Electricity Maps** live grid carbon intensity | `ELECTRICITY_MAPS_TOKEN` |
| **WattTime v3** live MOER data | `WATTTIME_USER`, `WATTTIME_PASS` |
| **Google Analytics 4** live functional unit counts | `GA4_PROPERTY_ID`, `GOOGLE_APPLICATION_CREDENTIALS` |
| **Azure DevOps** live pipeline run counts | `ADO_ORG`, `ADO_ORGS`, `ADO_PAT`, `ADO_PROJECTS` |
| **Mirantis MKE / Prometheus** live replica & CPU metrics | `KUBECONFIG_DIR` |

Without this file the backend will not start. Copy the example first:
```bash
cp .env.example .env
```

---

### 2. `ga4-service-account.json` — Google service account key
**Location:** `sci-carbon-dashboard/ga4-service-account.json`
*(path must match `GOOGLE_APPLICATION_CREDENTIALS` in `.env`)*

Required to pull live session/user counts from **Google Analytics 4** as the functional unit for GA-tracked applications (e.g. CustomerApp). Without this file GA4 functional units fall back to static hourly estimates.

To obtain:
1. Open [Google Cloud Console](https://console.cloud.google.com/) → IAM & Admin → Service Accounts
2. Create or select a service account and add a JSON key
3. In GA4 Admin → Property Access Management, grant the service account **Viewer** role
4. Download the key file and save it at the path above

---

### 3. `ucp-bundle-<username>/` — Mirantis MKE client bundle
**Location:** one level above `sci-carbon-dashboard/` — e.g. `ucp-bundle-<username>/` at the workspace root
Set `KUBECONFIG_DIR=../ucp-bundle-<username>` in `.env` (already the default).

Required to fetch **live Prometheus CPU/replica metrics** from the Mirantis MKE cluster. Without this directory the backend falls back to the static utilization values in each app's `config.json`.

To obtain:
1. Log in to your MKE UI → top-right user menu → **Client Bundle** → **New Client Bundle**
2. Download and extract the zip; the extracted folder is your bundle directory
3. Update `KUBECONFIG_DIR` in `.env` to point to the extracted folder

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/apps` | List all applications |
| GET | `/api/servers` | List server configurations |
| GET | `/api/regions` | List regions with carbon intensity |
| GET | `/api/sci/<app_name>` | Calculate SCI for one app |
| GET | `/api/sci/all` | Calculate SCI for all apps (ranked) |
| GET | `/api/recommendations/<app_name>` | Get optimization recommendations |
| GET | `/api/compare` | Full comparison (apps + recommendations + regions) |

### Example Response: `/api/compare`
```json
{
  "applications": [
    {
      "app": {
        "app_name": "CustomerApp",
        "sci": 0.02504197,
        "functional_unit": "order",
        "carbon_gco2e": 3130.246,
        "carbon_operational_gco2e": 2105.844,
        "carbon_embodied_gco2e": 1024.402,
        "total_energy_kwh": 0.050139,
        "server_type": "vsphere-worker-node",
        "server_count": 1,
        "region": "on-premises-datacenter",
        "cost_usd": 0
      },
      "recommendations": [
        {
          "type": "region_relocation",
          "priority": "high",
          "title": "Move to Oregon (us-west-2)",
          "carbon_reduction_percent": 33.3,
          "new_grid_intensity": 280,
          "renewable_percent": 72
        }
      ]
    },
    // ... more apps
  ],
  "regions": [
    {
      "name": "us-west-2",
      "location": "Oregon, USA",
      "intensity_gco2_kwh": 280,
      "source": "watttime-v3",
      "renewable_percent": 72
    },
    // ... more regions
  ]
}
```

---

## Optimization Logic

### Region Relocation
- Compares current region's carbon intensity with all available regions
- Checks if server type is available in target region
- Only recommends if carbon reduction ≥ 5%
- Priority: high (>20% reduction), medium (5-20%)

### Server Right-Sizing
- Triggers when CPU utilization < 40%
- Finds smaller instance from same provider
- Estimates carbon reduction proportional to vCPU ratio
- Includes cost impact analysis

### Time-Shifting
- Only for applications with batch workload patterns
- Recommends scheduling during regional low-carbon hours
- Based on renewable energy availability (solar peak, wind peak)

---

## WattTime Integration

### Free Tier Setup
1. Register at https://www.watttime.org/
2. Add credentials to `.env`:
   ```
   WATTTIME_USER=your-username
   WATTTIME_PASS=your-password
   ```

### Available Regions
Free tier provides **CAISO_NORTH** (California) with absolute MOER values. Other regions use fallback intensities from IEA 2022.

### How It Works
```
GET /v3/login → Bearer token (cached 30 min)
GET /v3/forecast?region=CAISO_NORTH&signal_type=co2_moer
  → first data-point = current 5-min window MOER (lbCO₂/MWh)
  → converted: value × 0.453592 / 1000 → gCO₂eq/kWh
```

---

## File Structure

```
sci-carbon-dashboard/
├── .env                        # secrets — copy from .env.example, never commit
├── .env.example                # committed template with all keys blank
├── ga4-service-account.json    # Google SA key — never commit (gitignored)
├── backend/
│   ├── app.py              # Flask API with optimization engine
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx         # React dashboard
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── nginx.conf
│   └── Dockerfile
├── data/
│   ├── servers/            # 5 server spec files (JSON)
│   ├── network/            # Network infrastructure (JSON)
│   ├── apps/               # 5 app folders with config + metrics
│   │   ├── CustomerApp/
│   │   │   ├── config.json
│   │   │   └── metrics-hourly.csv
│   │   └── ...
│   └── regions/
│       └── grid-regions.json
├── docker-compose.yml
├── .env.example
└── README.md
```

> **Note:** `ucp-bundle-<username>/` lives one level above this directory (workspace root). Set `KUBECONFIG_DIR` in `.env` to its path.

---

## Data Sources

### Embodied Carbon
- **Boavizta API** - CPU embodied emissions
- **Cloud Carbon Footprint** - Memory, storage, network, baseline server

### Operational Carbon
- **WattTime v3** - Real-time marginal operating emissions rate (MOER)
- **IEA 2022** - Static grid intensity averages (fallback)

### Energy Coefficients
- **Teads/Davy 2021** - CPU power curve [0,10,50,100] → [0.12,0.32,0.75,1.02]
- **Cloud Carbon Footprint** - Memory: 0.000392 kWh/GB/h
- **Cloud Carbon Footprint** - Network: 0.001 kWh/GB

### Server Specifications
- **AWS/Azure/GCP** - Published instance type specifications
- **Dell** - PowerEdge R740 product specifications

---

## Example Optimization Scenario

**CustomerService** (current state):
- 1× vSphere worker node on-premises
- Average CPU: 52%
- Carbon: ~85 gCO₂eq/hour
- Cost: CapEx model

**Recommendation**: No change needed - well-optimized
- CPU utilization within normal range
- Already on-premises (no cloud migration needed)

**CustomerApp** (current state):
- 1× vSphere worker node on-premises
- Carbon: ~72 gCO₂eq/hour

**Recommendation**: Scale down replicas during off-hours
- Weekend multiplier: 0.15 → opportunity to reduce replicas
- **Potential reduction: ~20%** during nights/weekends

---

## Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
flask --app app run --port 5000

# Frontend
cd frontend
npm install
npm run dev    # → http://localhost:5173
```

---

## References

- [Green Software Foundation - Impact Framework](https://if.greensoftware.foundation/)
- [ISO/IEC 21031 - SCI Specification](https://www.iso.org/standard/86612.html)
- [WattTime API v3 Documentation](https://docs.watttime.org/)
- [Cloud Carbon Footprint Methodology](https://www.cloudcarbonfootprint.org/docs/methodology/)
- [Boavizta API](https://doc.api.boavizta.org/)

---

## License
MIT
