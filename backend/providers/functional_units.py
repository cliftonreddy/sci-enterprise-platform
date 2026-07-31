"""
providers/functional_units.py
==============================
Functional unit count implementations.

The SCI engine walks a priority-ordered list of providers and uses the first
non-None result:  ADOProvider → GA4Provider → ConfigEstimateProvider

Concrete classes
----------------
  GA4Provider            — live page views from Google Analytics 4
  ADOProvider            — live pipeline runs from Azure DevOps (also exposes
                           get_details() for the dashboard's ADO detail panel)
  ConfigEstimateProvider — static fallback from the app's config.json
"""
from __future__ import annotations

import base64
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests as http

from .base import FunctionalUnitProvider


# ══════════════════════════════════════════════════════════════════════════════
#  GA4
# ══════════════════════════════════════════════════════════════════════════════

class GA4Provider(FunctionalUnitProvider):
    """
    Returns the 28-day rolling average page views per hour for apps that have a
    ``ga_page_title`` field in their config.json.  Uses the Google Analytics
    Data API v1beta with a service account (GOOGLE_APPLICATION_CREDENTIALS).
    """

    def __init__(self, property_id: str, cache_ttl: int = 3600) -> None:
        self._property_id = property_id
        self._cache_ttl   = cache_ttl
        self._cache: dict[str, tuple[float, float]] = {}   # app_name → (views/hr, ts)

    @property
    def source_label(self) -> str:
        return "google-analytics-live"

    def get_units_per_hour(self, app_name: str, config: dict) -> float | None:
        if not self._property_id:
            return None

        page_title = config.get("ga_page_title")
        if not page_title:
            return None

        # cache hit
        if app_name in self._cache:
            val, ts = self._cache[app_name]
            if time.time() - ts < self._cache_ttl:
                return val

        try:
            from google.analytics.data_v1beta import BetaAnalyticsDataClient
            from google.analytics.data_v1beta.types import (
                DateRange, Dimension, Filter, FilterExpression, Metric,
                RunReportRequest,
            )

            client   = BetaAnalyticsDataClient()
            response = client.run_report(RunReportRequest(
                property    = f"properties/{self._property_id}",
                date_ranges = [DateRange(start_date="28daysAgo", end_date="today")],
                metrics     = [Metric(name="screenPageViews")],
                dimensions  = [Dimension(name="pageTitle")],
                dimension_filter = FilterExpression(filter=Filter(
                    field_name   = "pageTitle",
                    string_filter = Filter.StringFilter(
                        match_type    = Filter.StringFilter.MatchType.CONTAINS,
                        value         = page_title,
                        case_sensitive = False,
                    ),
                )),
            ))

            total_views   = sum(int(row.metric_values[0].value) for row in response.rows)
            views_per_hour = total_views / (28 * 24)
            self._cache[app_name] = (views_per_hour, time.time())
            print(
                f"[ga4] {app_name}: {total_views} views/28d "
                f"→ {views_per_hour:.2f}/hr (pattern='{page_title}')",
                flush=True,
            )
            return views_per_hour

        except Exception as exc:
            print(f"[ga4] {app_name} query failed: {exc}", flush=True)
            return None


# ══════════════════════════════════════════════════════════════════════════════
#  AZURE DEVOPS
# ══════════════════════════════════════════════════════════════════════════════

class ADOProvider(FunctionalUnitProvider):
    """
    Returns the 28-day rolling average pipeline runs per hour across all
    configured ADO organisations.  Only returns a value for the "AzureDevOps"
    app; returns None for all other apps.

    All per-org and per-project HTTP calls are executed in parallel using a
    ThreadPoolExecutor so the full fetch completes in seconds rather than
    minutes for multi-org setups.
    """

    _POOL_SIZE = 8   # max parallel HTTP workers

    def __init__(
        self,
        pat:          str,
        org_list:     list[str],
        projects:     list[str] | None = None,
        cache_ttl:    int              = 3600,
        details_ttl:  int              = 300,
        agents_ttl:   int              = 60,
        app_name:     str              = "AzureDevOps",
    ) -> None:
        self._pat         = pat
        self._org_list    = org_list
        self._projects    = projects or []
        self._cache_ttl   = cache_ttl
        self._details_ttl = details_ttl
        self._agents_ttl  = agents_ttl
        self._app_name    = app_name

        self._cache:              dict[str, tuple[float, float]] = {}
        self._builds_by_project:  list[dict]                     = []
        self._agents_cache:       list                           = []
        self._agents_ts:          float                          = 0.0
        self._details_cache:      dict | None                    = None
        self._details_ts:         float                          = 0.0
        self._vsrm_down:          bool                           = False

    @property
    def source_label(self) -> str:
        return "azure-devops-live"

    # ── FunctionalUnitProvider interface ─────────────────────────────────────

    def get_units_per_hour(self, app_name: str, config: dict) -> float | None:
        if app_name != self._app_name:
            return None
        return self._fetch_runs_per_hour()

    # ── Public helper for the detail panel ───────────────────────────────────

    def get_details(self) -> dict | None:
        return self._fetch_details()

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        token_b64 = base64.b64encode(f":{self._pat}".encode()).decode()
        return {"Authorization": f"Basic {token_b64}", "Content-Type": "application/json"}

    def _get_org_projects(self, org: str, headers: dict) -> list[str]:
        """Return the project list for one org (uses fixed list if configured)."""
        if self._projects:
            return list(self._projects)
        try:
            r = http.get(
                f"https://dev.azure.com/{org}/_apis/projects",
                headers=headers, params={"api-version": "7.0"}, timeout=10,
            )
            r.raise_for_status()
            return [p["name"] for p in r.json().get("value", [])]
        except Exception as exc:
            print(f"[ado] project list failed for '{org}': {exc}", flush=True)
            return []

    def _fetch_project_builds(
        self, org: str, project: str, headers: dict, min_time: str
    ) -> tuple[str, str, int, list[int]]:
        """Fetch 28-day completed builds for one project. Returns (org, project, count, hour_dist)."""
        count = 0
        hour_dist = [0] * 24
        try:
            ct = None
            while True:
                params: dict = {
                    "api-version":  "7.0",
                    "statusFilter": "completed",
                    "minTime":       min_time,
                    "$top":          5000,
                }
                if ct:
                    params["continuationToken"] = ct
                r = http.get(
                    f"https://dev.azure.com/{org}/{urllib.parse.quote(project)}"
                    f"/_apis/build/builds",
                    headers=headers, params=params, timeout=20,
                )
                r.raise_for_status()
                data = r.json()
                for build in data.get("value", []):
                    count += 1
                    raw_t = build.get("startTime") or build.get("queueTime")
                    if raw_t:
                        try:
                            hour_dist[
                                datetime.fromisoformat(raw_t.rstrip("Z") + "+00:00").hour
                            ] += 1
                        except Exception:
                            pass
                ct = r.headers.get("x-ms-continuationtoken")
                if not ct:
                    break
        except Exception as exc:
            print(f"[ado] builds failed for '{org}/{project}': {exc}", flush=True)
        return org, project, count, hour_dist

    def _fetch_project_releases(
        self, org: str, project: str, headers: dict
    ) -> tuple[str, str, int]:
        """Fetch release count for one project. Returns (org/project key, org, count)."""
        try:
            r = http.get(
                f"https://vsrm.dev.azure.com/{org}/{urllib.parse.quote(project)}"
                f"/_apis/release/releases",
                headers=headers,
                params={"api-version": "7.0", "$top": 5000, "queryOrder": "descending"},
                timeout=10,
            )
            r.raise_for_status()
            return org, project, len(r.json().get("value", []))
        except http.exceptions.ConnectionError:
            return org, project, -1   # -1 signals vsrm unreachable
        except Exception:
            return org, project, 0

    def _fetch_org_agents(self, org: str, headers: dict) -> list[dict]:
        """Return all agents across all pools for one org (includes pool_id for job-stats lookup)."""
        agents: list[dict] = []
        try:
            r = http.get(
                f"https://dev.azure.com/{org}/_apis/distributedtask/pools",
                headers=headers, params={"api-version": "7.0"}, timeout=10,
            )
            r.raise_for_status()
            pool_ids = [(p["id"], p["name"]) for p in r.json().get("value", [])]
        except Exception as exc:
            print(f"[ado] agent pools failed for '{org}': {exc}", flush=True)
            return agents

        for pool_id, pool_name in pool_ids:
            try:
                ra = http.get(
                    f"https://dev.azure.com/{org}/_apis/distributedtask"
                    f"/pools/{pool_id}/agents",
                    headers=headers,
                    params={"api-version": "7.0", "includeCapabilities": "false",
                            "includeAssignedRequest": "true"},
                    timeout=10,
                )
                ra.raise_for_status()
                for agent in ra.json().get("value", []):
                    agents.append({
                        "org":         org,
                        "pool":        pool_name,
                        "pool_id":     pool_id,
                        "id":          agent["id"],
                        "name":        agent["name"],
                        "status":      agent.get("status", "unknown"),
                        "current_job": agent.get("assignedRequest", {})
                                           .get("definition", {}).get("name"),
                    })
            except Exception:
                pass
        return agents

    def _fetch_pool_job_stats(
        self, org: str, pool_id: int, agent_id: int, headers: dict, min_date: str
    ) -> tuple[int, int]:
        """
        Fetch completed job requests for ONE specific agent in ONE pool.
        Returns (jobs_28d, avg_duration_seconds).
        Uses the agentId filter so there is no ID-matching ambiguity.
        """
        jobs = 0
        total_s = 0.0
        try:
            r = http.get(
                f"https://dev.azure.com/{org}/_apis/distributedtask"
                f"/pools/{pool_id}/jobrequests",
                headers=headers,
                params={
                    "api-version":          "7.0",
                    "agentId":              agent_id,
                    "completedRequestCount": 5000,
                },
                timeout=10,
            )
            r.raise_for_status()
            for req in r.json().get("value", []):
                finish = req.get("finishTime")
                if not finish or finish < min_date:
                    continue
                jobs += 1
                receive = req.get("receiveTime") or req.get("assignTime")
                if receive:
                    try:
                        total_s += max(0.0, (
                            datetime.fromisoformat(finish.rstrip("Z") + "+00:00") -
                            datetime.fromisoformat(receive.rstrip("Z") + "+00:00")
                        ).total_seconds())
                    except Exception:
                        pass
        except Exception as exc:
            print(
                f"[ado] job requests failed agent {agent_id} pool {pool_id} '{org}': {exc}",
                flush=True,
            )
        avg = round(total_s / jobs) if jobs else 0
        return jobs, avg

    # ── Internal: parallel pipeline run count ────────────────────────────────

    def _fetch_runs_per_hour(self) -> float | None:
        if not self._org_list or not self._pat:
            return None

        cache_key = f"ado:{','.join(self._org_list)}"
        if cache_key in self._cache:
            val, ts = self._cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                return val

        headers  = self._headers()
        min_time = (datetime.now(timezone.utc) - timedelta(days=28)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        # ① discover projects for all orgs in parallel
        org_projects: dict[str, list[str]] = {}
        with ThreadPoolExecutor(max_workers=min(len(self._org_list), self._POOL_SIZE)) as ex:
            futures = {
                ex.submit(self._get_org_projects, org, headers): org
                for org in self._org_list
            }
            for fut in as_completed(futures):
                org_projects[futures[fut]] = fut.result()

        # ② fetch builds for all (org, project) pairs in parallel
        work = [
            (org, proj)
            for org, projs in org_projects.items()
            for proj in projs
        ]
        builds_by_project: list[dict] = []
        total_runs = 0

        with ThreadPoolExecutor(max_workers=self._POOL_SIZE) as ex:
            futures2 = {
                ex.submit(self._fetch_project_builds, org, proj, headers, min_time): (org, proj)
                for org, proj in work
            }
            for fut in as_completed(futures2):
                o, p, count, hour_dist = fut.result()
                total_runs += count
                if count:
                    builds_by_project.append({
                        "org": o, "project": p,
                        "builds": count, "hour_dist": hour_dist,
                    })

        orgs_queried = sum(1 for v in org_projects.values() if v)
        if orgs_queried == 0:
            return None

        self._builds_by_project = builds_by_project
        runs_per_hour = total_runs / (28 * 24)
        self._cache[cache_key] = (runs_per_hour, time.time())
        print(
            f"[ado] {total_runs} builds/28d across {orgs_queried} org(s) "
            f"→ {runs_per_hour:.2f}/hr",
            flush=True,
        )
        return runs_per_hour

    # ── Internal: parallel agent + release detail ─────────────────────────────

    def _fetch_details(self) -> dict | None:
        if not self._org_list or not self._pat:
            return None

        now = time.time()

        # full detail cache hit
        if self._details_cache and (now - self._details_ts) < self._details_ttl:
            if (now - self._agents_ts) >= self._agents_ttl:
                new_agents = self._fetch_agents()
                self._agents_cache = new_agents
                self._agents_ts    = now
                headers = self._headers()
                self._details_cache["agents"]            = new_agents
                self._details_cache["agent_utilization"] = self._build_agent_utilization(new_agents, headers)
                self._details_cache["utilization_summary"] = self._compute_utilization(new_agents)
            return self._details_cache

        headers = self._headers()

        # ensure build data is populated
        if not self._builds_by_project:
            self._fetch_runs_per_hour()

        # ① fetch agents for all orgs in parallel
        agents: list[dict] = []
        with ThreadPoolExecutor(max_workers=min(len(self._org_list), self._POOL_SIZE)) as ex:
            futures = {
                ex.submit(self._fetch_org_agents, org, headers): org
                for org in self._org_list
            }
            for fut in as_completed(futures):
                agents.extend(fut.result())
        self._agents_cache = agents
        self._agents_ts    = now

        # ② per-agent utilization (job stats from pool job-requests API)
        agent_utilization = self._build_agent_utilization(agents, headers)

        # ② fetch releases for all (org, project) pairs in parallel
        total_releases        = 0
        releases_by_project:  dict[str, int] = {}

        if not self._vsrm_down:
            # discover projects per org (reuse cached results if possible)
            release_work: list[tuple[str, str]] = []
            for org in self._org_list:
                projs = self._get_org_projects(org, headers)
                release_work.extend((org, p) for p in projs)

            with ThreadPoolExecutor(max_workers=self._POOL_SIZE) as ex:
                futures2 = {
                    ex.submit(self._fetch_project_releases, org, proj, headers): (org, proj)
                    for org, proj in release_work
                }
                for fut in as_completed(futures2):
                    o, p, cnt = fut.result()
                    if cnt == -1:                   # vsrm unreachable
                        self._vsrm_down = True
                        print("[ado] vsrm.dev.azure.com unreachable — skipping releases", flush=True)
                    elif cnt > 0:
                        total_releases += cnt
                        releases_by_project[f"{o}/{p}"] = cnt

        # ③ build result
        total_builds = sum(b["builds"] for b in self._builds_by_project)
        by_project   = {
            f"{b['org']}/{b['project']}": {
                "builds":           b["builds"],
                "hour_distribution": b["hour_dist"],
            }
            for b in self._builds_by_project
        }

        result: dict = {
            "credentials_configured": True,
            "orgs_queried":           self._org_list,
            "agents":                 agents,
            "agent_utilization":      agent_utilization,
            "utilization_summary":    self._compute_utilization(agents),
            "summary_28d": {
                "total_builds":     total_builds,
                "total_releases":   total_releases,
                "total_runs":       total_builds + total_releases,
                "builds_per_day":   round(total_builds   / 28, 1),
                "releases_per_day": round(total_releases / 28, 1),
                "by_project":       by_project,
            },
        }
        self._details_cache = result
        self._details_ts    = now
        return result

    def _fetch_agents(self) -> list[dict]:
        """Refresh agent list for all orgs in parallel."""
        headers = self._headers()
        agents: list[dict] = []
        with ThreadPoolExecutor(max_workers=min(len(self._org_list), self._POOL_SIZE)) as ex:
            futures = {
                ex.submit(self._fetch_org_agents, org, headers): org
                for org in self._org_list
            }
            for fut in as_completed(futures):
                agents.extend(fut.result())
        return agents

    def _build_agent_utilization(
        self, agents: list[dict], headers: dict
    ) -> list[dict]:
        """
        Returns a per-agent array — only agents with jobs_28d > 0 — sorted
        by jobs descending (matching the original 'N agents with activity' view).
        Uses the agentId-filtered job-requests endpoint per agent so there is
        no pool-level ID-matching ambiguity.
        """
        min_date = (
            datetime.now(timezone.utc) - timedelta(days=28)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        def fetch_one(agent: dict) -> dict | None:
            pool_id = agent.get("pool_id")
            if pool_id is None:
                return None
            jobs, avg_s = self._fetch_pool_job_stats(
                agent["org"], pool_id, agent["id"], headers, min_date
            )
            if jobs == 0:
                return None   # exclude inactive agents
            return {
                "org":            agent["org"],
                "id":             agent["id"],
                "name":           agent["name"],
                "pool":           agent["pool"],
                "jobs_28d":       jobs,
                "avg_duration_s": avg_s,
                "utilization_pct": 0,   # set below once we know max
            }

        rows: list[dict] = []
        with ThreadPoolExecutor(max_workers=self._POOL_SIZE) as ex:
            futures = {ex.submit(fetch_one, a): a for a in agents}
            for fut in as_completed(futures):
                result = fut.result()
                if result is not None:
                    rows.append(result)

        _WINDOW_S = 28 * 24 * 3600  # seconds in 28 days
        for r in rows:
            r["utilization_pct"] = round(
                min(r["jobs_28d"] * r["avg_duration_s"] / _WINDOW_S * 100, 100.0), 1
            )

        rows.sort(key=lambda r: r["jobs_28d"], reverse=True)
        return rows

    @staticmethod
    def _compute_utilization(agents: list) -> dict:
        total  = len(agents)
        busy   = sum(1 for a in agents if a.get("current_job"))
        online = sum(1 for a in agents if a.get("status") == "online")
        return {
            "total":    total,
            "online":   online,
            "busy":     busy,
            "idle":     online - busy,
            "pct_busy": round(busy / online * 100, 1) if online else 0,
        }


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG ESTIMATE (static fallback)
# ══════════════════════════════════════════════════════════════════════════════

class ConfigEstimateProvider(FunctionalUnitProvider):
    """
    Returns the ``average_per_hour`` value from the app's config.json.
    Always returns a value — acts as the last-resort fallback in the
    provider priority list.
    """

    @property
    def source_label(self) -> str:
        return "config-estimate"

    def get_units_per_hour(self, app_name: str, config: dict) -> float | None:
        return float(config.get("functional_unit", {}).get("average_per_hour", 1000))
