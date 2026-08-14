"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Loader2,
  PlayCircle,
  RefreshCw,
  ScanSearch,
  ShieldAlert,
} from "lucide-react";

import { notify } from "@/components/ui/sonner";
import { getApiUrl } from "@/utils/api";
import { formatFastApiDetail } from "@/utils/authErrors";

type IntegrityRun = {
  id: string;
  source: "api" | "cli";
  status: "running" | "completed" | "failed" | "timed_out";
  health: "unknown" | "healthy" | "warning" | "critical";
  timeout_seconds: number;
  workspace_count: number;
  completed_workspace_count: number;
  failed_workspace_count: number;
  artifact_count: number;
  integrity_failed: number;
  new_anomalies: number;
  duration_ms: number | null;
  failure_detail: string | null;
  started_at: string;
  completed_at: string | null;
};

type IntegrityHealth = {
  health: "healthy" | "warning" | "critical";
  reason: string;
  overdue: boolean;
  max_age_hours: number;
  checked_at: string;
  latest_run: IntegrityRun | null;
};

type IntegrityIncident = {
  id: string;
  workspace_id: string;
  workspace_name: string;
  scene_type: "general" | "bid";
  artifact_id: string;
  resource_title: string;
  detail_url: string;
  anomaly_types: string[];
  severity: "high" | "medium" | "low";
  status: "open" | "in_progress" | "resolved" | "accepted_risk" | "false_positive";
  authorization_paused: boolean;
  assigned_to_username: string | null;
  occurrence_count: number;
  resolution_note: string | null;
  first_detected_at: string;
  last_detected_at: string;
  resolved_at: string | null;
};

async function responseDetail(response: Response) {
  const payload = await response.json().catch(() => null);
  return payload?.detail === undefined
    ? `Request failed (${response.status})`
    : formatFastApiDetail(payload.detail);
}

function durationLabel(value: number | null) {
  if (value === null) return "—";
  if (value < 1000) return `${value} ms`;
  if (value < 60_000) return `${(value / 1000).toFixed(1)} s`;
  return `${(value / 60_000).toFixed(1)} min`;
}

const healthClasses = {
  healthy: "bg-[#ECFDF3] text-[#027A48]",
  warning: "bg-[#FFFAEB] text-[#B54708]",
  critical: "bg-[#FEF3F2] text-[#B42318]",
  unknown: "bg-[#F2F4F7] text-[#667085]",
};

const reasonLabels: Record<string, string> = {
  never_run: "No scan has run",
  run_in_progress: "Scan in progress",
  run_timed_out: "Latest scan timed out",
  last_run_failed: "Latest scan failed",
  schedule_overdue: "Scheduled scan overdue",
  integrity_anomalies: "Integrity anomalies detected",
  ok: "Scheduled scans healthy",
};

const anomalyLabels: Record<string, string> = {
  file_integrity: "File",
  snapshot_integrity: "Snapshot",
  citation_integrity: "Citations",
};

export default function DeliveryIntegrityOperationsPanel() {
  const [health, setHealth] = useState<IntegrityHealth | null>(null);
  const [runs, setRuns] = useState<IntegrityRun[]>([]);
  const [incidents, setIncidents] = useState<IntegrityIncident[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("active");
  const [sceneFilter, setSceneFilter] = useState("all");

  const load = useCallback(async (showError = true) => {
    try {
      const [healthResponse, runsResponse, incidentsResponse] = await Promise.all([
        fetch(getApiUrl("/api/v1/enterprise/admin/delivery-integrity-health"), {
          credentials: "include",
          cache: "no-store",
        }),
        fetch(getApiUrl("/api/v1/enterprise/admin/delivery-integrity-runs?limit=30"), {
          credentials: "include",
          cache: "no-store",
        }),
        fetch(getApiUrl("/api/v1/enterprise/admin/delivery-integrity-incidents?limit=200"), {
          credentials: "include",
          cache: "no-store",
        }),
      ]);
      for (const response of [healthResponse, runsResponse, incidentsResponse]) {
        if (!response.ok) throw new Error(await responseDetail(response));
      }
      setHealth((await healthResponse.json()) as IntegrityHealth);
      setRuns((await runsResponse.json()) as IntegrityRun[]);
      setIncidents((await incidentsResponse.json()) as IntegrityIncident[]);
    } catch (error) {
      if (showError) {
        notify.error(
          "Could not load delivery integrity operations",
          error instanceof Error ? error.message : "Please try again."
        );
      }
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(false), 15_000);
    return () => window.clearInterval(timer);
  }, [load]);

  const runScan = async () => {
    setBusy("run");
    try {
      const response = await fetch(
        getApiUrl("/api/v1/enterprise/admin/delivery-integrity-runs"),
        { method: "POST", credentials: "include" }
      );
      if (!response.ok) throw new Error(await responseDetail(response));
      const report = await response.json();
      notify.success(
        "Delivery integrity scan completed",
        `${report.workspace_count} workspaces · ${report.integrity_failed} anomalies.`
      );
      await load(false);
    } catch (error) {
      notify.error(
        "Could not run delivery integrity scan",
        error instanceof Error ? error.message : "Please try again."
      );
    } finally {
      setBusy(null);
    }
  };

  const recheck = async (incident: IntegrityIncident) => {
    setBusy(`recheck:${incident.id}`);
    try {
      const response = await fetch(
        getApiUrl(`/api/v1/enterprise/admin/delivery-integrity-incidents/${incident.id}/recheck`),
        { method: "POST", credentials: "include" }
      );
      if (!response.ok) throw new Error(await responseDetail(response));
      const updated = (await response.json()) as IntegrityIncident;
      notify.success(
        "Integrity recheck completed",
        updated.status === "resolved" ? "The incident was resolved and authorization resumed." : "The anomaly is still active."
      );
      await load(false);
    } catch (error) {
      notify.error("Recheck failed", error instanceof Error ? error.message : "Please try again.");
    } finally {
      setBusy(null);
    }
  };

  const transitionIncident = async (
    incident: IntegrityIncident,
    status: IntegrityIncident["status"]
  ) => {
    let resolutionNote: string | null = null;
    if (["resolved", "accepted_risk", "false_positive"].includes(status)) {
      resolutionNote = window.prompt("Enter a resolution note for the audit record:");
      if (!resolutionNote?.trim()) return;
    }
    setBusy(`incident:${incident.id}`);
    try {
      const response = await fetch(
        getApiUrl(`/api/v1/enterprise/admin/delivery-integrity-incidents/${incident.id}`),
        {
          method: "PATCH",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status, resolution_note: resolutionNote }),
        }
      );
      if (!response.ok) throw new Error(await responseDetail(response));
      notify.success("Incident updated");
      await load(false);
    } catch (error) {
      notify.error("Could not update incident", error instanceof Error ? error.message : "Please try again.");
    } finally {
      setBusy(null);
    }
  };

  const filteredIncidents = useMemo(
    () => incidents.filter((incident) => {
      const statusMatches = statusFilter === "all"
        || (statusFilter === "active" && ["open", "in_progress"].includes(incident.status))
        || incident.status === statusFilter;
      return statusMatches && (sceneFilter === "all" || incident.scene_type === sceneFilter);
    }),
    [incidents, sceneFilter, statusFilter]
  );

  const activeIncidentCount = incidents.filter((item) => item.authorization_paused).length;
  const latestRun = health?.latest_run;

  return (
    <section className="space-y-5">
      <div className="rounded-[12px] border border-[#EDEEEF] bg-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#FEF3F2]">
              <ShieldAlert className="h-4 w-4 text-[#D92D20]" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-[#101323]">Delivery integrity operations</h2>
              <p className="mt-0.5 text-xs text-[#667085]">
                Monitor scheduled scans, isolate unsafe deliveries, and verify remediation.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void load()}
              disabled={busy !== null}
              className="inline-flex h-10 items-center gap-2 rounded-full border border-[#D9DCE3] px-4 text-xs font-semibold text-[#344054] disabled:opacity-60"
            >
              <RefreshCw className="h-4 w-4" /> Refresh
            </button>
            <button
              type="button"
              onClick={() => void runScan()}
              disabled={busy !== null || latestRun?.status === "running"}
              className="inline-flex h-10 items-center gap-2 rounded-full bg-[#7C51F8] px-4 text-xs font-semibold text-white disabled:opacity-50"
            >
              {busy === "run" ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
              Run full scan
            </button>
          </div>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-[12px] border border-[#EDEEEF] bg-white p-5">
          <Activity className="h-4 w-4 text-[#635BFF]" />
          <p className="mt-4 text-xs text-[#667085]">Scheduler health</p>
          <p className="mt-1 text-xl font-semibold capitalize text-[#101323]">{health?.health || "loading"}</p>
          <p className="mt-1 text-[11px] text-[#98A2B3]">{health ? reasonLabels[health.reason] || health.reason : "Checking latest run"}</p>
        </div>
        <div className="rounded-[12px] border border-[#EDEEEF] bg-white p-5">
          <ShieldAlert className="h-4 w-4 text-[#D92D20]" />
          <p className="mt-4 text-xs text-[#667085]">Active incidents</p>
          <p className="mt-1 text-xl font-semibold text-[#101323]">{activeIncidentCount}</p>
          <p className="mt-1 text-[11px] text-[#98A2B3]">deliveries with authorization paused</p>
        </div>
        <div className="rounded-[12px] border border-[#EDEEEF] bg-white p-5">
          <ScanSearch className="h-4 w-4 text-[#B54708]" />
          <p className="mt-4 text-xs text-[#667085]">Latest coverage</p>
          <p className="mt-1 text-xl font-semibold text-[#101323]">{latestRun?.completed_workspace_count || 0}/{latestRun?.workspace_count || 0}</p>
          <p className="mt-1 text-[11px] text-[#98A2B3]">workspaces completed</p>
        </div>
        <div className="rounded-[12px] border border-[#EDEEEF] bg-white p-5">
          <Clock3 className="h-4 w-4 text-[#027A48]" />
          <p className="mt-4 text-xs text-[#667085]">Latest duration</p>
          <p className="mt-1 text-xl font-semibold text-[#101323]">{durationLabel(latestRun?.duration_ms ?? null)}</p>
          <p className="mt-1 text-[11px] text-[#98A2B3]">overdue after {health?.max_age_hours || 26} hours</p>
        </div>
      </div>

      <section className="overflow-hidden rounded-[12px] border border-[#EDEEEF] bg-white">
        <div className="border-b border-[#EDEEEF] px-6 py-4">
          <h3 className="text-sm font-semibold text-[#101323]">Scan history</h3>
          <p className="mt-1 text-xs text-[#667085]">Latest API and scheduled CLI batches. Running jobs refresh every 15 seconds.</p>
        </div>
        <div className="max-h-[360px] divide-y divide-[#EDEEEF] overflow-y-auto">
          {runs.length === 0 && <p className="px-6 py-10 text-center text-sm text-[#667085]">No persisted scans yet.</p>}
          {runs.map((run) => (
            <div key={run.id} className="grid gap-3 px-6 py-4 sm:grid-cols-[170px_130px_1fr_auto] sm:items-center">
              <div>
                <p className="text-xs font-semibold text-[#344054]">{new Date(run.started_at).toLocaleString()}</p>
                <p className="mt-1 text-[11px] uppercase text-[#98A2B3]">{run.source} · {durationLabel(run.duration_ms)}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase ${healthClasses[run.health]}`}>{run.health}</span>
                <span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-[10px] uppercase text-[#667085]">{run.status}</span>
              </div>
              <div>
                <p className="text-xs text-[#344054]">{run.completed_workspace_count}/{run.workspace_count} workspaces · {run.artifact_count} artifacts · {run.integrity_failed} anomalous</p>
                <p className={`mt-1 truncate text-[11px] ${run.failure_detail ? "text-[#B42318]" : "text-[#98A2B3]"}`}>{run.failure_detail || `${run.new_anomalies} newly detected anomalies`}</p>
              </div>
              {run.status === "completed" ? <CheckCircle2 className="h-4 w-4 text-[#12B76A]" /> : run.status === "running" ? <Loader2 className="h-4 w-4 animate-spin text-[#7C51F8]" /> : <AlertTriangle className="h-4 w-4 text-[#D92D20]" />}
            </div>
          ))}
        </div>
      </section>

      <section className="overflow-hidden rounded-[12px] border border-[#EDEEEF] bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#EDEEEF] px-6 py-4">
          <div>
            <h3 className="text-sm font-semibold text-[#101323]">Integrity incidents</h3>
            <p className="mt-1 text-xs text-[#667085]">Active incidents pause new delivery authorizations until recheck or an audited decision.</p>
          </div>
          <div className="flex gap-2">
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="h-9 rounded-lg border border-[#D9DCE3] bg-white px-3 text-xs text-[#344054]">
              <option value="active">Active</option><option value="all">All statuses</option><option value="open">Open</option><option value="in_progress">In progress</option><option value="resolved">Resolved</option><option value="accepted_risk">Accepted risk</option><option value="false_positive">False positive</option>
            </select>
            <select value={sceneFilter} onChange={(event) => setSceneFilter(event.target.value)} className="h-9 rounded-lg border border-[#D9DCE3] bg-white px-3 text-xs text-[#344054]">
              <option value="all">All scenes</option><option value="general">General PPT</option><option value="bid">Bid PPT</option>
            </select>
          </div>
        </div>
        <div className="divide-y divide-[#EDEEEF]">
          {filteredIncidents.length === 0 && <p className="px-6 py-10 text-center text-sm text-[#667085]">No incidents match these filters.</p>}
          {filteredIncidents.map((incident) => (
            <div key={incident.id} className="space-y-3 px-6 py-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-semibold text-[#101323]">{incident.resource_title}</p>
                    <span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-[10px] uppercase text-[#667085]">{incident.scene_type}</span>
                    <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase ${incident.authorization_paused ? "bg-[#FEF3F2] text-[#B42318]" : "bg-[#ECFDF3] text-[#027A48]"}`}>{incident.status.replace("_", " ")}</span>
                  </div>
                  <p className="mt-1 text-xs text-[#667085]">{incident.workspace_name} · detected {new Date(incident.first_detected_at).toLocaleString()} · seen {incident.occurrence_count} times</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {incident.anomaly_types.map((type) => <span key={type} className="rounded-md bg-[#FFF4ED] px-2 py-1 text-[10px] font-semibold text-[#B54708]">{anomalyLabels[type] || type}</span>)}
                    {incident.assigned_to_username && <span className="rounded-md bg-[#F4F3FF] px-2 py-1 text-[10px] text-[#5146E5]">Assigned to {incident.assigned_to_username}</span>}
                  </div>
                  {incident.resolution_note && <p className="mt-2 text-[11px] text-[#667085]">Resolution: {incident.resolution_note}</p>}
                </div>
                <a href={incident.detail_url} className="inline-flex items-center gap-1 text-xs font-semibold text-[#5146E5]">Open delivery <ExternalLink className="h-3.5 w-3.5" /></a>
              </div>
              {incident.authorization_paused && (
                <div className="flex flex-wrap gap-2">
                  {incident.status === "open" && <button type="button" disabled={busy !== null} onClick={() => void transitionIncident(incident, "in_progress")} className="h-8 rounded-full border border-[#D9DCE3] px-3 text-[11px] font-semibold text-[#344054]">Start handling</button>}
                  <button type="button" disabled={busy !== null} onClick={() => void recheck(incident)} className="inline-flex h-8 items-center gap-1.5 rounded-full bg-[#7C51F8] px-3 text-[11px] font-semibold text-white disabled:opacity-50">{busy === `recheck:${incident.id}` && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Recheck</button>
                  <button type="button" disabled={busy !== null} onClick={() => void transitionIncident(incident, "accepted_risk")} className="h-8 rounded-full border border-[#FEC84B] px-3 text-[11px] font-semibold text-[#B54708]">Accept risk</button>
                  <button type="button" disabled={busy !== null} onClick={() => void transitionIncident(incident, "false_positive")} className="h-8 rounded-full border border-[#D9DCE3] px-3 text-[11px] font-semibold text-[#667085]">False positive</button>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </section>
  );
}
