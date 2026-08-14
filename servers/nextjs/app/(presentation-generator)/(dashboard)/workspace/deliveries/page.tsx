"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertTriangle, ArrowLeft, CheckCircle2, FileCheck2, RefreshCw, Search, ShieldAlert } from "lucide-react";

import { EnterpriseApi, type DeliveryCenterResponse, type DeliveryIntegrityScanResponse, type WorkspaceResponse } from "@/app/(presentation-generator)/services/api/enterprise";

export default function DeliveryCenterPage() {
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [data, setData] = useState<DeliveryCenterResponse | null>(null);
  const [scans, setScans] = useState<DeliveryIntegrityScanResponse[]>([]);
  const [sceneType, setSceneType] = useState("");
  const [status, setStatus] = useState("");
  const [integrity, setIntegrity] = useState("");
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    EnterpriseApi.getWorkspaces().then((rows) => {
      const admins = rows.filter((item) => ["owner", "admin"].includes(item.current_user_role));
      setWorkspaces(admins);
      const requested = new URLSearchParams(window.location.search).get("workspace_id");
      const requestedIntegrity = new URLSearchParams(window.location.search).get("integrity");
      if (["passed", "failed"].includes(requestedIntegrity || "")) setIntegrity(requestedIntegrity || "");
      setWorkspaceId(admins.some((item) => item.id === requested) ? requested || "" : admins[0]?.id || "");
    }).catch((cause) => setError(cause instanceof Error ? cause.message : "空间加载失败"));
  }, []);

  const load = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const [center, history] = await Promise.all([
        EnterpriseApi.getDeliveryCenter(workspaceId, { sceneType, status, integrity, q: appliedQuery }),
        EnterpriseApi.getDeliveryIntegrityScans(workspaceId),
      ]);
      setData(center);
      setScans(history);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "交付中心加载失败");
    } finally { setLoading(false); }
  }, [appliedQuery, integrity, sceneType, status, workspaceId]);

  useEffect(() => { void load(); }, [load]);
  const search = (event: FormEvent) => { event.preventDefault(); setAppliedQuery(query.trim()); };
  const runScan = async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      await EnterpriseApi.runDeliveryIntegrityScan(workspaceId);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "完整性巡检失败");
      setLoading(false);
    }
  };

  return <main className="min-h-screen bg-[#F7F7FA] px-5 py-8 text-[#101828] sm:px-8">
    <div className="mx-auto max-w-7xl">
      <Link href={`/workspace${workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : ""}`} className="inline-flex items-center gap-2 text-sm text-[#475467]"><ArrowLeft className="h-4 w-4" />返回工作台</Link>
      <header className="mt-5 flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-medium text-[#635BFF]">企业治理</p><h1 className="mt-1 text-2xl font-semibold">交付中心</h1><p className="mt-2 text-sm text-[#667085]">统一核验通用 PPT 与竞标交付件、下载使用和撤销风险。</p></div><div className="flex gap-2"><select value={workspaceId} onChange={(event) => setWorkspaceId(event.target.value)} className="h-10 rounded-lg border border-[#D9DCE3] bg-white px-3 text-sm">{workspaces.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><button type="button" onClick={() => void runScan()} disabled={loading} className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#17171B] px-3 text-sm text-white disabled:opacity-40"><ShieldAlert className="h-4 w-4" />立即巡检</button><button type="button" onClick={() => void load()} className="inline-flex h-10 items-center gap-2 rounded-lg border border-[#D9DCE3] bg-white px-3 text-sm"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />刷新</button></div></header>
      {error && <p className="mt-4 rounded-xl bg-[#FEF2F2] p-3 text-sm text-[#B42318]">{error}</p>}
      <section className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">{[
        ["全部交付", data?.summary.total ?? 0, ""], ["可交付", data?.summary.ready ?? 0, "text-[#027A48]"], ["已撤销", data?.summary.revoked ?? 0, "text-[#B42318]"], ["完整性异常", data?.summary.integrity_failed ?? 0, "text-[#B42318]"], ["累计下载", data?.summary.downloads ?? 0, ""], ["有效授权", data?.summary.active_grants ?? 0, "text-[#4238CA]"],
      ].map(([label, value, color]) => <div key={String(label)} className="rounded-2xl border border-[#EAECF0] bg-white p-4"><p className="text-xs text-[#667085]">{label}</p><p className={`mt-2 text-2xl font-semibold ${color}`}>{value}</p></div>)}</section>
      <section className="mt-5 rounded-2xl border border-[#E3E4EA] bg-white p-4"><form onSubmit={search} className="flex flex-wrap gap-2"><select value={sceneType} onChange={(event) => setSceneType(event.target.value)} className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm"><option value="">全部场景</option><option value="general">通用 PPT</option><option value="bid">竞标 PPT</option></select><select value={status} onChange={(event) => setStatus(event.target.value)} className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm"><option value="">全部状态</option><option value="ready">可交付</option><option value="revoked">已撤销</option></select><select value={integrity} onChange={(event) => setIntegrity(event.target.value)} className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm"><option value="">全部完整性</option><option value="passed">验证通过</option><option value="failed">验证异常</option></select><div className="flex min-w-[260px] flex-1"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索文稿、项目编号、文件名或 SHA-256" className="h-10 min-w-0 flex-1 rounded-l-lg border border-r-0 border-[#D9DCE3] px-3 text-sm" /><button className="inline-flex h-10 items-center gap-1 rounded-r-lg bg-[#635BFF] px-4 text-sm text-white"><Search className="h-4 w-4" />搜索</button></div></form></section>
      <section className="mt-5 overflow-hidden rounded-2xl border border-[#E3E4EA] bg-white"><div className="grid grid-cols-[minmax(220px,1.5fr)_90px_110px_120px_110px_100px] gap-3 border-b border-[#EAECF0] bg-[#F8F9FC] px-5 py-3 text-xs font-medium text-[#667085]"><span>交付对象</span><span>场景/格式</span><span>状态</span><span>完整性</span><span>下载/授权</span><span>操作</span></div>{data?.items.map((item) => <article key={`${item.scene_type}:${item.artifact_id}`} className="grid grid-cols-[minmax(220px,1.5fr)_90px_110px_120px_110px_100px] gap-3 border-b border-[#F0F1F3] px-5 py-4 text-xs last:border-0"><div className="min-w-0"><p className="truncate text-sm font-medium">{item.resource_title}</p><p className="mt-1 truncate text-[#667085]">{item.resource_code ? `${item.resource_code} · ` : ""}V{item.version_no} · {item.file_name}</p><p className="mt-1 truncate font-mono text-[10px] text-[#98A2B3]">{item.sha256}</p></div><div><p>{item.scene_type === "bid" ? "竞标" : "通用"}</p><p className="mt-1 uppercase text-[#667085]">{item.format}</p></div><div><span className={`rounded-full px-2 py-1 ${item.status === "ready" ? "bg-[#ECFDF3] text-[#027A48]" : "bg-[#FEF2F2] text-[#B42318]"}`}>{item.status === "ready" ? "可交付" : "已撤销"}</span></div><div className="flex items-start gap-1">{item.integrity_status === "passed" ? <CheckCircle2 className="h-4 w-4 text-[#039855]" /> : <ShieldAlert className="h-4 w-4 text-[#D92D20]" />}<div><p className={item.integrity_status === "passed" ? "text-[#027A48]" : "text-[#B42318]"}>{item.integrity_status === "passed" ? "三层通过" : "验证异常"}</p><p className="mt-1 text-[10px] text-[#98A2B3]">引用 {item.citation_integrity === null ? "不适用" : item.citation_count}</p></div></div><div><p>{item.download_count} 次下载</p><p className="mt-1 text-[#667085]">{item.active_grant_count}/{item.grant_count} 有效</p></div><Link href={item.detail_url} className="inline-flex h-8 items-center justify-center gap-1 rounded-lg border border-[#D9DCE3]"><FileCheck2 className="h-3.5 w-3.5" />详情</Link></article>)}{!loading && !data?.items.length && <p className="p-12 text-center text-sm text-[#98A2B3]">当前筛选条件下暂无交付件</p>}{loading && <p className="p-12 text-center text-sm text-[#667085]">正在校验交付件完整性…</p>}</section>
      {(data?.summary.integrity_failed ?? 0) > 0 && <div className="mt-4 flex items-start gap-2 rounded-xl border border-[#FDA29B] bg-[#FEF2F2] p-4 text-sm text-[#B42318]"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />检测到交付文件、冻结快照或引用证据异常，请暂停下载授权并进入详情核查。</div>}
      <section className="mt-5 rounded-2xl border border-[#E3E4EA] bg-white p-5"><div className="flex items-center justify-between"><h2 className="font-semibold">巡检历史</h2><span className="text-xs text-[#98A2B3]">保留在工作区审计日志</span></div>{scans.length ? <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{scans.slice(0, 6).map((scan) => <div key={scan.id} className="rounded-xl bg-[#F8F9FC] p-3 text-xs"><div className="flex items-center justify-between"><span>{new Date(scan.created_at).toLocaleString()}</span><span className={scan.integrity_failed ? "text-[#B42318]" : "text-[#027A48]"}>{scan.integrity_failed ? `${scan.integrity_failed} 项异常` : "全部通过"}</span></div><p className="mt-2 text-[#667085]">扫描 {scan.total} 个交付件 · 新增异常 {scan.new_anomaly_ids.length}</p></div>)}</div> : <p className="mt-3 rounded-xl bg-[#F8F9FC] p-4 text-sm text-[#667085]">尚未执行持久化巡检；点击“立即巡检”建立首条基线。</p>}</section>
    </div>
  </main>;
}
