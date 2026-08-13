"use client";

import { useState } from "react";
import {
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
  const [busy, setBusy] = useState<"scan" | "execute" | null>(null);
  const [maxDelete, setMaxDelete] = useState(100);

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
    </section>
  );
}
