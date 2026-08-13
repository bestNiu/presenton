"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Library, Loader2, Plus, Save, Star, X } from "lucide-react";

import {
  EnterpriseApi,
  type AssetItemResponse,
  type AssetScopeType,
  type AssetPersonalizedItemResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";

interface EnterpriseAssetPanelProps {
  workspaceId: string;
  entryId: string;
  currentSlideIndex: number;
  currentSlideId?: string;
  onPresentationChanged: () => Promise<void>;
}

const scopeLabel: Record<AssetScopeType, string> = {
  personal: "个人",
  workspace: "空间",
  enterprise: "企业",
};

export default function EnterpriseAssetPanel({
  workspaceId,
  entryId,
  currentSlideIndex,
  currentSlideId,
  onPresentationChanged,
}: EnterpriseAssetPanelProps) {
  const [open, setOpen] = useState(false);
  const [assets, setAssets] = useState<AssetItemResponse[]>([]);
  const [personalized, setPersonalized] = useState<Record<string, AssetPersonalizedItemResponse[]>>({});
  const [view, setView] = useState<"all" | "recommended" | "recent" | "favorites">("recommended");
  const [name, setName] = useState("");
  const [tags, setTags] = useState("");
  const [scope, setScope] = useState<"personal" | "workspace">("personal");
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [assetRows, recommended, recent, favorites] = await Promise.all([
        EnterpriseApi.getAssets(workspaceId, { assetType: "page" }),
        EnterpriseApi.getPersonalizedAssets(workspaceId, "recommended", { limit: 30 }),
        EnterpriseApi.getPersonalizedAssets(workspaceId, "recent", { limit: 30 }),
        EnterpriseApi.getPersonalizedAssets(workspaceId, "favorites", { limit: 30 }),
      ]);
      setAssets(assetRows);
      setPersonalized({ recommended, recent, favorites });
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "资产加载失败");
    }
  }, [workspaceId]);

  useEffect(() => {
    if (open) void load();
  }, [load, open]);

  useEffect(() => {
    if (!open || !assets.some((asset) => ["queued", "rendering"].includes(asset.preview_status))) return;
    const timer = window.setInterval(() => void load(), 3000);
    return () => window.clearInterval(timer);
  }, [assets, load, open]);

  const visibleAssets = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    const favoriteIds = new Set((personalized.favorites || []).map((item) => item.asset.id));
    const source: AssetPersonalizedItemResponse[] = view === "all" ? assets.map((asset) => ({ asset, is_favorite: favoriteIds.has(asset.id), last_used_at: null, recommendation_score: null, recommendation_reasons: [] })) : (personalized[view] || []);
    return source.filter(
      (item) => item.asset.asset_type === "page"
    ).filter(
      (item) => {
        const asset = item.asset;
        return (
          asset.status !== "offline" &&
          asset.status !== "archived" &&
          asset.authorization_status !== "revoked" &&
          (!asset.expires_at || new Date(asset.expires_at).getTime() > Date.now()) &&
          (!keyword ||
            asset.name.toLowerCase().includes(keyword) ||
            asset.tags.some((tag) => tag.toLowerCase().includes(keyword)))
        );
      }
    );
  }, [assets, personalized, query, view]);

  const toggleFavorite = async (item: { asset: AssetItemResponse; is_favorite?: boolean }) => {
    setPending(`favorite:${item.asset.id}`);
    try {
      await EnterpriseApi.setAssetFavorite(item.asset.id, !item.is_favorite);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "收藏状态更新失败");
    } finally { setPending(""); }
  };

  const saveCurrentSlide = async (event: FormEvent) => {
    event.preventDefault();
    if (!currentSlideId || !name.trim()) return;
    setPending("save");
    setError(null);
    try {
      await EnterpriseApi.saveSlideAsAsset(workspaceId, entryId, currentSlideId, {
        scope_type: scope,
        name: name.trim(),
        tags: tags.split(",").map((item) => item.trim()).filter(Boolean),
      });
      setName("");
      setTags("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "当前页保存失败");
    } finally {
      setPending("");
    }
  };

  const insert = async (asset: AssetItemResponse) => {
    setPending(asset.id);
    setError(null);
    try {
      const compatibility = await EnterpriseApi.getAssetCompatibility(
        asset.id,
        workspaceId,
        entryId
      );
      if (!compatibility.can_insert) {
        setError(compatibility.issues.map((issue) => issue.message).join("；") || "该资产与当前文稿不兼容");
        return;
      }
      if (
        compatibility.status === "warning" &&
        !window.confirm(`${compatibility.issues.map((issue) => issue.message).join("；")}。是否按保留源样式方式插入？`)
      ) return;
      await EnterpriseApi.insertAssetPage(
        asset.id,
        workspaceId,
        entryId,
        currentSlideIndex
      );
      await Promise.all([load(), onPresentationChanged()]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "资产页插入失败");
    } finally {
      setPending("");
    }
  };

  const createVersion = async (asset: AssetItemResponse) => {
    if (!currentSlideId) return;
    setPending(`version:${asset.id}`);
    setError(null);
    try {
      await EnterpriseApi.saveSlideAsAssetVersion(
        workspaceId,
        entryId,
        currentSlideId,
        asset.id
      );
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "资产新版本创建失败");
    } finally { setPending(""); }
  };

  return <>
    <button type="button" onClick={() => setOpen(true)} className="fixed bottom-32 right-5 z-40 inline-flex h-11 items-center gap-2 rounded-full border border-[#D9DCE3] bg-white px-4 text-sm font-medium text-[#344054] shadow-lg xl:bottom-5 xl:right-[515px]">
      <Library className="h-4 w-4 text-[#635BFF]" />资产库
    </button>
    {open && <aside className="fixed inset-y-3 right-3 z-[80] flex w-[min(420px,calc(100vw-24px))] flex-col overflow-hidden rounded-2xl border border-[#E3E4EA] bg-white shadow-2xl">
      <header className="flex items-center justify-between border-b border-[#EAECF0] px-4 py-3">
        <div><h2 className="text-sm font-semibold text-[#101828]">通用页面资产库</h2><p className="mt-0.5 text-xs text-[#667085]">保存当前页，或复制资产到第 {currentSlideIndex + 1} 页之后</p></div>
        <button type="button" onClick={() => setOpen(false)} className="rounded-full p-2 hover:bg-[#F2F4F7]"><X className="h-4 w-4" /></button>
      </header>
      <form onSubmit={saveCurrentSlide} className="space-y-2 border-b border-[#EAECF0] p-4">
        <div className="flex items-center gap-2 text-xs font-medium text-[#344054]"><Save className="h-4 w-4" />保存当前页为资产</div>
        <input value={name} onChange={(event) => setName(event.target.value)} placeholder="资产名称" className="h-9 w-full rounded-lg border border-[#D9DCE3] px-3 text-xs" />
        <div className="flex gap-2"><input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="标签，逗号分隔" className="h-9 min-w-0 flex-1 rounded-lg border border-[#D9DCE3] px-3 text-xs" /><select value={scope} onChange={(event) => setScope(event.target.value as "personal" | "workspace")} className="h-9 rounded-lg border border-[#D9DCE3] px-2 text-xs"><option value="personal">个人资产</option><option value="workspace">空间资产</option></select></div>
        <button disabled={!currentSlideId || !name.trim() || pending === "save"} className="flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-[#635BFF] text-xs text-white disabled:opacity-40">{pending === "save" && <Loader2 className="h-3.5 w-3.5 animate-spin" />}保存快照</button>
      </form>
      <div className="flex min-h-0 flex-1 flex-col p-4">
        <div className="mb-3 grid grid-cols-4 gap-1 rounded-lg bg-[#F2F4F7] p-1">{(["recommended", "recent", "favorites", "all"] as const).map((item) => <button key={item} onClick={() => setView(item)} className={`rounded-md px-1 py-1.5 text-[10px] ${view === item ? "bg-white font-medium text-[#4238CA] shadow-sm" : "text-[#667085]"}`}>{item === "recommended" ? "推荐" : item === "recent" ? "最近" : item === "favorites" ? "收藏" : "全部"}</button>)}</div>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索名称或标签" className="h-9 rounded-lg border border-[#D9DCE3] px-3 text-xs" />
        {error && <p className="mt-2 rounded-lg bg-[#FEF2F2] p-2 text-xs text-[#B42318]">{error}</p>}
        <div className="mt-3 min-h-0 flex-1 space-y-2 overflow-y-auto">
          {visibleAssets.length === 0 && <p className="rounded-xl bg-[#F8F9FC] p-5 text-center text-xs text-[#667085]">暂无可复用页面资产</p>}
          {visibleAssets.map((item) => { const asset = item.asset; return <article key={asset.id} className="rounded-xl border border-[#EAECF0] p-3">
            <div className="flex items-start justify-between gap-2"><div className="min-w-0"><p className="truncate text-sm font-medium text-[#101828]">{asset.name}</p><p className="mt-1 text-[11px] text-[#667085]">{scopeLabel[asset.scope_type]} · v{asset.version_no}{asset.is_latest ? " 当前版" : ""} · {asset.status === "published" ? "已发布" : "草稿"} · 复用 {asset.usage_count} 次</p></div><button type="button" onClick={() => void toggleFavorite(item)} className="rounded p-1 hover:bg-[#F2F4F7]" title="收藏"><Star className={`h-4 w-4 ${item.is_favorite ? "fill-[#F5B700] text-[#F5B700]" : "text-[#98A2B3]"}`} /></button></div>
            {EnterpriseApi.getAssetPreviewUrl(asset) && <div className="mt-2 aspect-[16/9] rounded-lg border border-[#EAECF0] bg-cover bg-center" role="img" aria-label={`${asset.name}预览图`} style={{ backgroundImage: `url(${EnterpriseApi.getAssetPreviewUrl(asset)})` }} />}
            {["queued", "rendering"].includes(asset.preview_status) && <p className="mt-2 inline-flex items-center gap-1 text-[10px] text-[#667085]"><Loader2 className="h-3 w-3 animate-spin" />正在生成高清预览</p>}
            {item.recommendation_reasons?.length > 0 && <p className="mt-2 text-[10px] text-[#667085]">{item.recommendation_reasons.slice(0, 2).join(" · ")}</p>}
            {asset.tags.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{asset.tags.map((tag) => <span key={tag} className="rounded bg-[#F2F1FF] px-1.5 py-0.5 text-[10px] text-[#4238CA]">{tag}</span>)}</div>}
            <div className="mt-3 grid grid-cols-2 gap-2"><button type="button" disabled={Boolean(pending)} onClick={() => void insert(asset)} className="flex h-8 items-center justify-center gap-1 rounded-lg border border-[#CBC7FF] text-xs text-[#4238CA] disabled:opacity-40">{pending === asset.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}兼容检查并插入</button><button type="button" disabled={Boolean(pending) || !currentSlideId || asset.status !== "published"} onClick={() => void createVersion(asset)} className="flex h-8 items-center justify-center gap-1 rounded-lg border border-[#D9DCE3] text-xs text-[#475467] disabled:opacity-40">{pending === `version:${asset.id}` && <Loader2 className="h-3.5 w-3.5 animate-spin" />}当前页建新版</button></div>
          </article>; })}
        </div>
      </div>
    </aside>}
  </>;
}
