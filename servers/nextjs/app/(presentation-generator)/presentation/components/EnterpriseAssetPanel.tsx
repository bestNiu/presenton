"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Archive, Library, Loader2, Plus, Save, X } from "lucide-react";

import {
  EnterpriseApi,
  type AssetItemResponse,
  type AssetScopeType,
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
  const [name, setName] = useState("");
  const [tags, setTags] = useState("");
  const [scope, setScope] = useState<"personal" | "workspace">("personal");
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setAssets(await EnterpriseApi.getAssets(workspaceId, { assetType: "page" }));
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "资产加载失败");
    }
  }, [workspaceId]);

  useEffect(() => {
    if (open) void load();
  }, [load, open]);

  const visibleAssets = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return assets.filter(
      (asset) =>
        asset.status !== "offline" &&
        asset.status !== "archived" &&
        asset.authorization_status !== "revoked" &&
        (!asset.expires_at || new Date(asset.expires_at).getTime() > Date.now()) &&
        (!keyword ||
          asset.name.toLowerCase().includes(keyword) ||
          asset.tags.some((tag) => tag.toLowerCase().includes(keyword)))
    );
  }, [assets, query]);

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
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索名称或标签" className="h-9 rounded-lg border border-[#D9DCE3] px-3 text-xs" />
        {error && <p className="mt-2 rounded-lg bg-[#FEF2F2] p-2 text-xs text-[#B42318]">{error}</p>}
        <div className="mt-3 min-h-0 flex-1 space-y-2 overflow-y-auto">
          {visibleAssets.length === 0 && <p className="rounded-xl bg-[#F8F9FC] p-5 text-center text-xs text-[#667085]">暂无可复用页面资产</p>}
          {visibleAssets.map((asset) => <article key={asset.id} className="rounded-xl border border-[#EAECF0] p-3">
            <div className="flex items-start justify-between gap-2"><div className="min-w-0"><p className="truncate text-sm font-medium text-[#101828]">{asset.name}</p><p className="mt-1 text-[11px] text-[#667085]">{scopeLabel[asset.scope_type]} · {asset.status === "published" ? "已发布" : "草稿"} · 复用 {asset.usage_count} 次</p></div><Archive className="h-4 w-4 shrink-0 text-[#98A2B3]" /></div>
            {asset.tags.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{asset.tags.map((tag) => <span key={tag} className="rounded bg-[#F2F1FF] px-1.5 py-0.5 text-[10px] text-[#4238CA]">{tag}</span>)}</div>}
            <button type="button" disabled={Boolean(pending)} onClick={() => void insert(asset)} className="mt-3 flex h-8 w-full items-center justify-center gap-1 rounded-lg border border-[#CBC7FF] text-xs text-[#4238CA] disabled:opacity-40">{pending === asset.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}插入到当前页后</button>
          </article>)}
        </div>
      </div>
    </aside>}
  </>;
}
