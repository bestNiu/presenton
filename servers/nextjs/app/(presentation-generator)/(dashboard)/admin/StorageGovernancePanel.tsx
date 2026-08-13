"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Database,
  HardDrive,
  Loader2,
  PlayCircle,
  ScanSearch,
  ShieldCheck,
  Trash2,
} from "lucide-react";

import { notify } from "@/components/ui/sonner";
import { getApiUrl } from "@/utils/api";
import { formatFastApiDetail } from "@/utils/authErrors";

type LifecycleCandidate = {
  object_key: string;
  reason: "orphan" | "revoked_presentation_delivery" | "revoked_bid_delivery";
  size_bytes: number;
  last_modified: string;
};

type LifecycleReport = {
  run_id: string;
  mode: "dry_run" | "execute";
  backend: "local" | "s3";
  scanned_count: number;
  stored_bytes: number;
  referenced_count: number;
  protected_count: number;
  protected_bytes: number;
  missing_referenced_count: number;
  candidate_count: number;
  candidate_bytes: number;
  orphan_candidate_count: number;
  revoked_candidate_count: number;
  deleted_count: number;
  deleted_bytes: number;
  truncated: boolean;
  candidates: LifecycleCandidate[];
  completed_at: string;
};

type LifecycleHistory = {
  id: string;
  source: "api" | "cli";
  mode: "dry_run" | "execute";
  backend: "local" | "s3" | null;
  status: "running" | "completed" | "failed";
  health: "unknown" | "healthy" | "warning" | "critical";
  stored_bytes: number;
  missing_referenced_count: number;
  candidate_count: number;
  candidate_bytes: number;
  deleted_count: number;
  deleted_bytes: number;
  failure_detail: string | null;
  started_at: string;
  completed_at: string | null;
};

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

const reasonLabel: Record<LifecycleCandidate["reason"], string> = {
  orphan: "Orphan object",
  revoked_presentation_delivery: "Revoked presentation",
  revoked_bid_delivery: "Revoked bid delivery",
};

async function responseDetail(response: Response) {
  const payload = await response.json().catch(() => null);
  return payload?.detail === undefined
    ? `Request failed (${response.status})`
    : formatFastApiDetail(payload.detail);
}

export default function StorageGovernancePanel() {
  const [report, setReport] = useState<LifecycleReport | null>(null);
  const [history, setHistory] = useState<LifecycleHistory[]>([]);
  const [busy, setBusy] = useState<"scan" | "execute" | null>(null);
  const [maxDelete, setMaxDelete] = useState(100);

  const loadHistory = useCallback(async () => {
    const response = await fetch(
      getApiUrl("/api/v1/enterprise/admin/storage/lifecycle-runs?limit=30"),
      { credentials: "include", cache: "no-store" }
    );
    if (!response.ok) throw new Error(await responseDetail(response));
    setHistory((await response.json()) as LifecycleHistory[]);
  }, []);

  useEffect(() => {
    void loadHistory().catch((error) =>
      notify.error(
        "Could not load storage history",
        error instanceof Error ? error.message : "Please try again."
      )
    );
  }, [loadHistory]);

  const run = async (execute: boolean) => {
    if (
      execute &&
      !window.confirm(
        `Delete up to ${maxDelete} eligible objects from private storage? Active objects remain protected.`
      )
    ) {
      return;
    }
    setBusy(execute ? "execute" : "scan");
    try {
      const response = await fetch(
        getApiUrl("/api/v1/enterprise/admin/storage/lifecycle-runs"),
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ execute, max_delete: maxDelete }),
        }
      );
      if (!response.ok) throw new Error(await responseDetail(response));
      const next = (await response.json()) as LifecycleReport;
      setReport(next);
      await loadHistory();
      if (execute) {
        notify.success(
          "Storage cleanup completed",
          `${next.deleted_count} objects and ${formatBytes(next.deleted_bytes)} removed.`
        );
      } else {
        notify.success(
          "Storage scan completed",
          `${next.candidate_count} eligible objects found.`
        );
      }
    } catch (error) {
      notify.error(
        execute ? "Storage cleanup failed" : "Storage scan failed",
        error instanceof Error ? error.message : "Please try again."
      );
    } finally {
      setBusy(null);
    }
  };

  const metrics = report
    ? [
        { label: "Stored", value: formatBytes(report.stored_bytes), detail: `${report.scanned_count} objects`, icon: HardDrive },
        { label: "Protected", value: formatBytes(report.protected_bytes), detail: `${report.protected_count} active objects`, icon: ShieldCheck },
        { label: "Eligible", value: formatBytes(report.candidate_bytes), detail: `${report.candidate_count} objects`, icon: Trash2 },
        { label: "Missing", value: String(report.missing_referenced_count), detail: "expected references", icon: AlertTriangle },
      ]
    : [];

  return (
    <section className="space-y-5">
      <div className="rounded-[12px] border border-[#EDEEEF] bg-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#F4F3FF]">
              <Database className="h-4 w-4 text-[#5146E5]" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-[#101323]">Object storage governance</h2>
              <p className="mt-0.5 text-xs text-[#667085]">
                Scan first, then remove only aged revoked deliveries and orphan objects.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 text-xs text-[#667085]">
              Batch limit
              <input
                type="number"
                min={1}
                max={1000}
                value={maxDelete}
                onChange={(event) => setMaxDelete(Math.max(1, Math.min(1000, Number(event.target.value) || 1)))}
                className="h-10 w-24 rounded-lg border border-[#E1E1E5] px-3 text-sm outline-none focus:border-[#7A5AF8]"
              />
            </label>
            <button
              type="button"
              onClick={() => void run(false)}
              disabled={busy !== null}
              className="inline-flex h-10 items-center gap-2 rounded-full border border-[#D9DCE3] bg-white px-4 text-xs font-semibold text-[#344054] disabled:opacity-60"
            >
              {busy === "scan" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanSearch className="h-4 w-4" />}
              Dry-run scan
            </button>
            <button
              type="button"
              onClick={() => void run(true)}
              disabled={busy !== null || !report || report.candidate_count === 0}
              className="inline-flex h-10 items-center gap-2 rounded-full bg-[#D92D20] px-4 text-xs font-semibold text-white disabled:opacity-40"
            >
              {busy === "execute" ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
              Execute cleanup
            </button>
          </div>
        </div>
      </div>

      {!report ? (
        <div className="rounded-[12px] border border-dashed border-[#D9DCE3] bg-white px-6 py-12 text-center">
          <ScanSearch className="mx-auto h-7 w-7 text-[#98A2B3]" />
          <p className="mt-3 text-sm font-semibold text-[#344054]">No lifecycle report yet</p>
          <p className="mt-1 text-xs text-[#667085]">Run a dry-run scan to inspect capacity and deletion candidates.</p>
        </div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {metrics.map((metric) => (
              <div key={metric.label} className="rounded-[12px] border border-[#EDEEEF] bg-white p-5">
                <metric.icon className="h-4 w-4 text-[#635BFF]" />
                <p className="mt-4 text-xs text-[#667085]">{metric.label}</p>
                <p className="mt-1 text-xl font-semibold text-[#101323]">{metric.value}</p>
                <p className="mt-1 text-[11px] text-[#98A2B3]">{metric.detail}</p>
              </div>
            ))}
          </div>

          <section className="overflow-hidden rounded-[12px] border border-[#EDEEEF] bg-white">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#EDEEEF] px-6 py-4">
              <div>
                <h3 className="text-sm font-semibold text-[#101323]">Lifecycle candidates</h3>
                <p className="mt-1 text-xs text-[#667085]">
                  {report.orphan_candidate_count} orphan · {report.revoked_candidate_count} revoked · backend {report.backend}
                </p>
              </div>
              <p className="text-[11px] text-[#98A2B3]">
                {report.mode === "execute" ? `${report.deleted_count} deleted · ` : ""}
                {new Date(report.completed_at).toLocaleString()}
              </p>
            </div>
            <div className="max-h-[420px] divide-y divide-[#EDEEEF] overflow-y-auto">
              {report.candidates.length === 0 && <p className="px-6 py-10 text-center text-sm text-[#667085]">No eligible objects.</p>}
              {report.candidates.map((candidate) => (
                <div key={candidate.object_key} className="flex flex-wrap items-center justify-between gap-3 px-6 py-4">
                  <div className="min-w-0 flex-1">
                    <code className="block truncate text-xs text-[#344054]">{candidate.object_key}</code>
                    <p className="mt-1 text-[11px] text-[#98A2B3]">{reasonLabel[candidate.reason]} · {new Date(candidate.last_modified).toLocaleString()}</p>
                  </div>
                  <span className="text-xs font-semibold text-[#667085]">{formatBytes(candidate.size_bytes)}</span>
                </div>
              ))}
            </div>
            {report.candidate_count > report.candidates.length && (
              <p className="border-t border-[#EDEEEF] px-6 py-3 text-xs text-[#B54708]">Showing the first 100 candidates. Use small cleanup batches.</p>
            )}
          </section>
        </>
      )}

      <section className="overflow-hidden rounded-[12px] border border-[#EDEEEF] bg-white">
        <div className="flex items-center justify-between border-b border-[#EDEEEF] px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#F4F3FF]">
              <Activity className="h-4 w-4 text-[#5146E5]" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[#101323]">Run history and health</h3>
              <p className="mt-0.5 text-xs text-[#667085]">Latest 30 API and scheduled CLI runs.</p>
            </div>
          </div>
          <button type="button" onClick={() => void loadHistory()} className="inline-flex h-9 items-center gap-2 rounded-full border border-[#EDEEEF] px-3 text-xs text-[#667085]">
            <ScanSearch className="h-3.5 w-3.5" /> Refresh
          </button>
        </div>
        <div className="divide-y divide-[#EDEEEF]">
          {history.length === 0 && <p className="px-6 py-10 text-center text-sm text-[#667085]">No persisted runs yet.</p>}
          {history.map((run) => {
            const healthClass = run.health === "healthy" ? "bg-[#ECFDF3] text-[#027A48]" : run.health === "warning" ? "bg-[#FFFAEB] text-[#B54708]" : run.health === "critical" ? "bg-[#FEF3F2] text-[#B42318]" : "bg-[#F2F4F7] text-[#667085]";
            return (
              <div key={run.id} className="grid gap-3 px-6 py-4 sm:grid-cols-[150px_110px_1fr_auto] sm:items-center">
                <div>
                  <p className="text-xs font-semibold text-[#344054]">{new Date(run.started_at).toLocaleString()}</p>
                  <p className="mt-1 text-[11px] uppercase text-[#98A2B3]">{run.source} · {run.backend || "pending"}</p>
                </div>
                <div className="flex gap-2">
                  <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase ${healthClass}`}>{run.health}</span>
                  <span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-[10px] uppercase text-[#667085]">{run.mode}</span>
                </div>
                <div>
                  <p className="text-xs text-[#344054]">{formatBytes(run.stored_bytes)} stored · {run.candidate_count} eligible · {run.deleted_count} deleted</p>
                  <p className={`mt-1 truncate text-[11px] ${run.failure_detail ? "text-[#B42318]" : "text-[#98A2B3]"}`}>{run.failure_detail || `${run.missing_referenced_count} missing references · ${formatBytes(run.candidate_bytes)} candidate capacity`}</p>
                </div>
                <span className="text-[11px] font-semibold uppercase text-[#667085]">{run.status}</span>
              </div>
            );
          })}
        </div>
      </section>
    </section>
  );
}
