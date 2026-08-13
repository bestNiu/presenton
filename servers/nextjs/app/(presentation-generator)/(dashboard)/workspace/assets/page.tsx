"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Archive, ArrowLeft, Library, Loader2, Search, Send, ShieldCheck, Star, X } from "lucide-react";

import {
  EnterpriseApi,
  type AssetItemResponse,
  type AssetAnalyticsResponse,
  type AssetPromotionResponse,
  type AssetStatus,
  type WorkspaceResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";

const statusLabel: Record<AssetStatus, string> = {
  draft: "草稿",
  published: "已发布",
  offline: "已下线",
  archived: "已归档",
};

const typeLabel: Record<string, string> = {
  page: "页面",
  chart: "图表",
  image: "图片",
  logo: "Logo",
  copy: "文案",
  component: "组件",
};

export default function AssetCenterPage() {
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [assets, setAssets] = useState<AssetItemResponse[]>([]);
  const [analytics, setAnalytics] = useState<AssetAnalyticsResponse | null>(null);
  const [myPromotions, setMyPromotions] = useState<AssetPromotionResponse[]>([]);
  const [reviewPromotions, setReviewPromotions] = useState<AssetPromotionResponse[]>([]);
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | AssetStatus>("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [promotionTarget, setPromotionTarget] = useState<AssetItemResponse | null>(null);
  const [justification, setJustification] = useState("");
  const [desensitizationNotes, setDesensitizationNotes] = useState("");
  const [authorizationConfirmed, setAuthorizationConfirmed] = useState(false);
  const [decisionComments, setDecisionComments] = useState<Record<string, string>>({});
  const [selectedAssetIds, setSelectedAssetIds] = useState<string[]>([]);
  const [favoriteAssetIds, setFavoriteAssetIds] = useState<string[]>([]);
  const [favoritesOnly, setFavoritesOnly] = useState(false);

  useEffect(() => {
    EnterpriseApi.getWorkspaces()
      .then((rows) => {
        setWorkspaces(rows);
        const requested = new URLSearchParams(window.location.search).get("workspace_id");
        setWorkspaceId(rows.some((item) => item.id === requested) ? requested || "" : rows[0]?.id || "");
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : "空间加载失败"));
  }, []);

  const load = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    setError(null);
    try {
      const [assetRows, mineRows, reviewRows, analyticsResult, favoriteRows] = await Promise.all([
        EnterpriseApi.getAssets(workspaceId, {
          assetType: typeFilter || undefined,
          status: statusFilter || undefined,
        }),
        EnterpriseApi.getAssetPromotionRequests(undefined, "mine"),
        EnterpriseApi.getAssetPromotionRequests(undefined, "review"),
        EnterpriseApi.getAssetAnalytics(workspaceId),
        EnterpriseApi.getPersonalizedAssets(workspaceId, "favorites", { limit: 100 }),
      ]);
      setAssets(assetRows);
      setMyPromotions(mineRows);
      setReviewPromotions(reviewRows);
      setAnalytics(analyticsResult);
      setFavoriteAssetIds(favoriteRows.map((item) => item.asset.id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "资产加载失败");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, typeFilter, workspaceId]);

  useEffect(() => { void load(); }, [load]);

  const visibleAssets = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return assets.filter((asset) => (!favoritesOnly || favoriteAssetIds.includes(asset.id)) && (!keyword || asset.name.toLowerCase().includes(keyword) || asset.tags.some((tag) => tag.toLowerCase().includes(keyword))));
  }, [assets, favoriteAssetIds, favoritesOnly, query]);

  const workspaceRole = workspaces.find((item) => item.id === workspaceId)?.current_user_role;
  const canManageAsset = (asset: AssetItemResponse) =>
    asset.scope_type === "personal" ||
    (asset.scope_type === "workspace" && ["owner", "admin"].includes(workspaceRole || "viewer"));

  const transition = async (asset: AssetItemResponse, action: "publish" | "offline" | "archive") => {
    setPending(asset.id);
    setError(null);
    try {
      await EnterpriseApi.transitionAsset(asset.id, action);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "资产状态更新失败");
    } finally {
      setPending("");
    }
  };

  const bulkTransition = async (action: "publish" | "offline" | "archive") => {
    if (selectedAssetIds.length === 0) return;
    setPending("bulk");
    setError(null);
    try {
      await EnterpriseApi.bulkTransitionAssets(selectedAssetIds, action);
      setSelectedAssetIds([]);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "批量治理失败");
    } finally {
      setPending("");
    }
  };

  const toggleFavorite = async (asset: AssetItemResponse) => {
    const next = !favoriteAssetIds.includes(asset.id);
    setPending(`favorite:${asset.id}`);
    setError(null);
    try {
      await EnterpriseApi.setAssetFavorite(asset.id, next);
      setFavoriteAssetIds((current) => next ? [...current, asset.id] : current.filter((id) => id !== asset.id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "收藏状态更新失败");
    } finally { setPending(""); }
  };

  const submitPromotion = async () => {
    if (!promotionTarget || !justification.trim() || !desensitizationNotes.trim() || !authorizationConfirmed) return;
    setPending(`promote:${promotionTarget.id}`);
    setError(null);
    try {
      const targetScope = promotionTarget.scope_type === "personal" ? "workspace" : "enterprise";
      await EnterpriseApi.createAssetPromotionRequest(promotionTarget.id, {
        target_scope_type: targetScope,
        ...(targetScope === "workspace" ? { target_workspace_id: workspaceId } : {}),
        justification: justification.trim(),
        desensitization_notes: desensitizationNotes.trim(),
        authorization_confirmed: true,
      });
      setPromotionTarget(null);
      setJustification("");
      setDesensitizationNotes("");
      setAuthorizationConfirmed(false);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "资产提升申请提交失败");
    } finally {
      setPending("");
    }
  };

  const decidePromotion = async (request: AssetPromotionResponse, action: "approve" | "reject") => {
    const comment = decisionComments[request.id]?.trim();
    if (!comment) return;
    setPending(`decision:${request.id}`);
    setError(null);
    try {
      await EnterpriseApi.decideAssetPromotionRequest(request.id, action, comment);
      setDecisionComments((current) => ({ ...current, [request.id]: "" }));
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "资产提升审批失败");
    } finally {
      setPending("");
    }
  };

  return <main className="min-h-screen bg-[#F6F7FB] px-5 py-8 text-[#101828]">
    <div className="mx-auto max-w-6xl">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3"><Link href={`/workspace${workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : ""}`} className="rounded-lg border border-[#D9DCE3] bg-white p-2"><ArrowLeft className="h-4 w-4" /></Link><div><h1 className="flex items-center gap-2 text-xl font-semibold"><Library className="h-5 w-5 text-[#635BFF]" />企业资产中心</h1><p className="mt-1 text-sm text-[#667085]">统一管理可跨场景复用的 PPT 页面、图表、图片、文案与组件</p></div></div>
        <select value={workspaceId} onChange={(event) => setWorkspaceId(event.target.value)} className="h-10 rounded-lg border border-[#D9DCE3] bg-white px-3 text-sm">{workspaces.map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}</select>
      </header>

      <section className="mt-6 grid gap-3 rounded-2xl border border-[#EAECF0] bg-white p-4 md:grid-cols-[1fr_180px_180px_auto]">
        <label className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-[#98A2B3]" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索名称或标签" className="h-10 w-full rounded-lg border border-[#D9DCE3] pl-9 pr-3 text-sm" /></label>
        <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm"><option value="">全部类型</option>{Object.entries(typeLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as "" | AssetStatus)} className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm"><option value="">全部状态</option>{Object.entries(statusLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <button onClick={() => setFavoritesOnly((value) => !value)} className={`inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm ${favoritesOnly ? "border-[#F5B700] bg-[#FFF9E6] text-[#8A6100]" : "border-[#D9DCE3] text-[#475467]"}`}><Star className={`h-4 w-4 ${favoritesOnly ? "fill-[#F5B700] text-[#F5B700]" : ""}`} />收藏</button>
      </section>

      {analytics && <section className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {[{ label: "可见资产", value: analytics.total_assets, detail: `已发布 ${analytics.published_assets}` }, { label: "累计复用", value: analytics.total_reuses, detail: `近 30 天 ${analytics.reuses_last_30_days}` }, { label: "覆盖文稿", value: analytics.unique_presentations, detail: `使用者 ${analytics.unique_users}` }, { label: "即将到期", value: analytics.expiring_within_7_days, detail: "未来 7 天" }, { label: "已过期", value: analytics.expired_assets, detail: "需及时治理" }].map((metric) => <div key={metric.label} className="rounded-2xl border border-[#EAECF0] bg-white p-4"><p className="text-xs text-[#667085]">{metric.label}</p><p className="mt-2 text-2xl font-semibold">{metric.value}</p><p className="mt-1 text-[11px] text-[#98A2B3]">{metric.detail}</p></div>)}
      </section>}
      {selectedAssetIds.length > 0 && <div className="sticky top-3 z-20 mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#CBC7FF] bg-[#F8F7FF] px-4 py-3 shadow-sm"><span className="text-sm font-medium text-[#4238CA]">已选择 {selectedAssetIds.length} 项</span><div className="flex gap-2"><button disabled={Boolean(pending)} onClick={() => void bulkTransition("publish")} className="rounded-lg bg-[#635BFF] px-3 py-1.5 text-xs text-white disabled:opacity-40">批量发布</button><button disabled={Boolean(pending)} onClick={() => void bulkTransition("offline")} className="rounded-lg border border-[#D9DCE3] bg-white px-3 py-1.5 text-xs disabled:opacity-40">批量下线</button><button disabled={Boolean(pending)} onClick={() => void bulkTransition("archive")} className="rounded-lg border border-[#FECACA] bg-white px-3 py-1.5 text-xs text-[#B42318] disabled:opacity-40">批量归档</button><button onClick={() => setSelectedAssetIds([])} className="px-2 text-xs text-[#667085]">取消</button></div></div>}

      {error && <p className="mt-4 rounded-xl bg-[#FEF2F2] p-3 text-sm text-[#B42318]">{error}</p>}
      {(reviewPromotions.some((item) => item.status === "pending") || myPromotions.length > 0) && <section className="mt-5 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-[#EAECF0] bg-white p-5"><h2 className="flex items-center gap-2 text-sm font-semibold"><ShieldCheck className="h-4 w-4 text-[#635BFF]" />待我审批</h2><div className="mt-3 space-y-3">{reviewPromotions.filter((item) => item.status === "pending").length === 0 && <p className="rounded-lg bg-[#F8F9FC] p-3 text-xs text-[#667085]">当前空间暂无待审批申请</p>}{reviewPromotions.filter((item) => item.status === "pending").map((item) => <article key={item.id} className="rounded-xl border border-[#EAECF0] p-3"><p className="text-sm font-medium">{item.asset_name_snapshot}</p><p className="mt-1 text-xs text-[#667085]">用途：{item.justification}</p><p className="mt-1 text-xs text-[#667085]">脱敏：{item.desensitization_notes}</p><input value={decisionComments[item.id] || ""} onChange={(event) => setDecisionComments((current) => ({ ...current, [item.id]: event.target.value }))} placeholder="填写审批意见" className="mt-3 h-8 w-full rounded-lg border border-[#D9DCE3] px-2 text-xs" /><div className="mt-2 flex justify-end gap-2"><button disabled={!decisionComments[item.id]?.trim() || Boolean(pending)} onClick={() => void decidePromotion(item, "reject")} className="rounded-lg border border-[#FECACA] px-3 py-1.5 text-xs text-[#B42318] disabled:opacity-40">驳回</button><button disabled={!decisionComments[item.id]?.trim() || Boolean(pending)} onClick={() => void decidePromotion(item, "approve")} className="rounded-lg bg-[#635BFF] px-3 py-1.5 text-xs text-white disabled:opacity-40">通过并发布</button></div></article>)}</div></div>
        <div className="rounded-2xl border border-[#EAECF0] bg-white p-5"><h2 className="flex items-center gap-2 text-sm font-semibold"><Send className="h-4 w-4 text-[#635BFF]" />我的提升申请</h2><div className="mt-3 space-y-2">{myPromotions.length === 0 && <p className="rounded-lg bg-[#F8F9FC] p-3 text-xs text-[#667085]">尚未提交提升申请</p>}{myPromotions.slice(0, 5).map((item) => <div key={item.id} className="flex items-center justify-between rounded-xl border border-[#EAECF0] p-3"><div><p className="text-sm font-medium">{item.asset_name_snapshot}</p><p className="mt-1 text-xs text-[#667085]">目标：{item.target_scope_type === "workspace" ? "空间资产" : "企业资产"}{item.decision_comment ? ` · ${item.decision_comment}` : ""}</p></div><span className={`rounded-full px-2 py-1 text-xs ${item.status === "approved" ? "bg-[#ECFDF3] text-[#027A48]" : item.status === "rejected" ? "bg-[#FEF2F2] text-[#B42318]" : "bg-[#FFF4E5] text-[#B54708]"}`}>{item.status === "approved" ? "已通过" : item.status === "rejected" ? "已驳回" : "审批中"}</span></div>)}</div></div>
      </section>}
      {loading ? <div className="flex justify-center py-20"><Loader2 className="h-6 w-6 animate-spin text-[#635BFF]" /></div> : <section className="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {visibleAssets.length === 0 && <p className="col-span-full rounded-2xl border border-dashed border-[#D0D5DD] bg-white p-12 text-center text-sm text-[#667085]">暂无符合条件的资产，可在文稿编辑器中将当前页保存到资产库。</p>}
        {visibleAssets.map((asset) => <article key={asset.id} className="flex min-h-52 flex-col rounded-2xl border border-[#EAECF0] bg-white p-5 shadow-sm">
          <div className="mb-2 flex items-center justify-between"><button type="button" onClick={() => void toggleFavorite(asset)} className="rounded p-1 hover:bg-[#F2F4F7]" title="收藏资产"><Star className={`h-4 w-4 ${favoriteAssetIds.includes(asset.id) ? "fill-[#F5B700] text-[#F5B700]" : "text-[#98A2B3]"}`} /></button>{canManageAsset(asset) && <label className="flex items-center justify-end gap-1 text-[10px] text-[#667085]"><input type="checkbox" checked={selectedAssetIds.includes(asset.id)} onChange={(event) => setSelectedAssetIds((current) => event.target.checked ? [...current, asset.id] : current.filter((id) => id !== asset.id))} />选择治理</label>}</div>
          <div className="mb-4 aspect-[16/9] overflow-hidden rounded-xl border border-[#EAECF0] bg-[#F8F9FC] p-3" style={{ borderTop: `4px solid ${asset.preview.accent || "#635BFF"}` }}><div className="flex h-full flex-col justify-between"><div><p className="line-clamp-2 text-sm font-semibold leading-5 text-[#101828]">{asset.preview.title || asset.name}</p>{asset.preview.subtitle && <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-[#667085]">{asset.preview.subtitle}</p>}</div><div className="flex items-center justify-between text-[9px] uppercase tracking-wide text-[#98A2B3]"><span>{asset.preview.layout || asset.asset_type}</span><span>{asset.preview.element_count || 0} elements</span></div></div></div>
          <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="text-xs font-medium text-[#635BFF]">{typeLabel[asset.asset_type] || asset.asset_type} · {asset.scope_type === "personal" ? "个人" : asset.scope_type === "workspace" ? "空间" : "企业"}</p><h2 className="mt-2 truncate text-base font-semibold">{asset.name}</h2></div><div className="flex flex-col items-end gap-1"><span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-xs text-[#475467]">{statusLabel[asset.status]}</span>{asset.authorization_status === "revoked" && <span className="rounded-full bg-[#FEF2F2] px-2 py-1 text-[10px] text-[#B42318]">授权撤销</span>}{asset.expires_at && new Date(asset.expires_at).getTime() <= Date.now() && <span className="rounded-full bg-[#FEF2F2] px-2 py-1 text-[10px] text-[#B42318]">授权过期</span>}</div></div>
          <p className="mt-3 line-clamp-2 text-xs leading-5 text-[#667085]">{asset.description || "暂无说明"}</p>
          <div className="mt-3 flex flex-wrap gap-1">{asset.tags.map((tag) => <span key={tag} className="rounded bg-[#F2F1FF] px-2 py-1 text-[10px] text-[#4238CA]">{tag}</span>)}</div>
          <div className="mt-auto border-t border-[#EAECF0] pt-4"><div className="flex items-center justify-between"><span className="text-xs text-[#667085]">已复用 {asset.usage_count} 次</span>{canManageAsset(asset) && <div className="flex gap-2">{asset.status === "draft" && <button disabled={pending === asset.id} onClick={() => void transition(asset, "publish")} className="rounded-lg bg-[#635BFF] px-3 py-1.5 text-xs text-white disabled:opacity-40">发布</button>}{asset.status === "published" && <button disabled={pending === asset.id} onClick={() => void transition(asset, "offline")} className="rounded-lg border border-[#D9DCE3] px-3 py-1.5 text-xs disabled:opacity-40">下线</button>}{asset.status !== "archived" && asset.status !== "published" && <button disabled={pending === asset.id} onClick={() => void transition(asset, "archive")} className="rounded-lg border border-[#FECACA] px-2 py-1.5 text-[#B42318] disabled:opacity-40" title="归档"><Archive className="h-3.5 w-3.5" /></button>}</div>}</div>{asset.status !== "offline" && asset.status !== "archived" && asset.scope_type !== "enterprise" && <button onClick={() => setPromotionTarget(asset)} className="mt-3 w-full rounded-lg bg-[#F2F1FF] py-2 text-xs font-medium text-[#4238CA]">申请提升为{asset.scope_type === "personal" ? "空间" : "企业"}资产</button>}</div>
        </article>)}
      </section>}
    </div>
    {promotionTarget && <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/35 p-4"><div className="w-full max-w-lg rounded-2xl bg-white p-5 shadow-2xl"><div className="flex items-start justify-between"><div><h2 className="text-base font-semibold">申请提升资产</h2><p className="mt-1 text-xs text-[#667085]">{promotionTarget.name} → {promotionTarget.scope_type === "personal" ? "当前工作空间" : "企业资产库"}</p></div><button onClick={() => setPromotionTarget(null)} className="rounded-full p-2 hover:bg-[#F2F4F7]"><X className="h-4 w-4" /></button></div><label className="mt-4 block text-xs font-medium text-[#344054]">复用目的<textarea value={justification} onChange={(event) => setJustification(event.target.value)} rows={3} className="mt-1 w-full rounded-lg border border-[#D9DCE3] p-3 text-xs" placeholder="说明适用场景和公共价值" /></label><label className="mt-3 block text-xs font-medium text-[#344054]">脱敏处理说明<textarea value={desensitizationNotes} onChange={(event) => setDesensitizationNotes(event.target.value)} rows={3} className="mt-1 w-full rounded-lg border border-[#D9DCE3] p-3 text-xs" placeholder="说明已移除的客户、项目、价格或个人信息" /></label><label className="mt-3 flex items-start gap-2 text-xs leading-5 text-[#475467]"><input type="checkbox" checked={authorizationConfirmed} onChange={(event) => setAuthorizationConfirmed(event.target.checked)} className="mt-1" />我确认该内容具备目标范围内的使用授权，且已完成必要脱敏。</label><button onClick={() => void submitPromotion()} disabled={!justification.trim() || !desensitizationNotes.trim() || !authorizationConfirmed || Boolean(pending)} className="mt-4 flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-[#635BFF] text-sm text-white disabled:opacity-40">{pending.startsWith("promote:") && <Loader2 className="h-4 w-4 animate-spin" />}提交审批</button></div></div>}
  </main>;
}
