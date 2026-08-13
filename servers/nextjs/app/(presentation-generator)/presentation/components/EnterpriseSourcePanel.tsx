"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, FileSearch, Loader2, Plus, Search, Trash2, X } from "lucide-react";

import {
  EnterpriseApi,
  type EnterpriseKnowledgeSearchItemResponse,
  type PresentationSourceCitationPreviewResponse,
  type PresentationSourceCitationResponse,
  type PresentationSourceCitationSummaryResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";

interface EnterpriseSourcePanelProps {
  workspaceId: string;
  entryId: string;
  currentSlideIndex: number;
  currentSlideId?: string;
}

export default function EnterpriseSourcePanel({ workspaceId, entryId, currentSlideIndex, currentSlideId }: EnterpriseSourcePanelProps) {
  const [open, setOpen] = useState(false);
  const [citations, setCitations] = useState<PresentationSourceCitationResponse[]>([]);
  const [summary, setSummary] = useState<PresentationSourceCitationSummaryResponse | null>(null);
  const [preview, setPreview] = useState<PresentationSourceCitationPreviewResponse | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<EnterpriseKnowledgeSearchItemResponse[]>([]);
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [canEdit, setCanEdit] = useState(false);

  const load = useCallback(async () => {
    try {
      const [rows, citationSummary, workspaces] = await Promise.all([
        EnterpriseApi.getPresentationCitations(workspaceId, entryId),
        EnterpriseApi.getPresentationCitationSummary(workspaceId, entryId),
        EnterpriseApi.getWorkspaces(),
      ]);
      setCitations(rows);
      setSummary(citationSummary);
      const workspace = workspaces.find((item) => item.id === workspaceId);
      setCanEdit(Boolean(workspace && !["viewer", "reviewer"].includes(workspace.current_user_role)));
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "引用来源加载失败");
    }
  }, [entryId, workspaceId]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { setPreview(null); }, [currentSlideId]);

  const currentCitations = useMemo(
    () => citations.filter((item) => item.slide_id === currentSlideId),
    [citations, currentSlideId]
  );
  const invalidCount = citations.filter((item) => item.status !== "valid").length;

  const search = async (event: FormEvent) => {
    event.preventDefault();
    if (!query.trim()) return;
    setPending("search");
    try {
      setResults(await EnterpriseApi.searchKnowledge(workspaceId, query.trim()));
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "资料检索失败");
    } finally { setPending(null); }
  };

  const add = async (item: EnterpriseKnowledgeSearchItemResponse) => {
    if (!currentSlideId) return;
    setPending(`add:${item.chunk_id}`);
    try {
      await EnterpriseApi.createPresentationCitation(workspaceId, entryId, { slide_id: currentSlideId, ...item.citation });
      await load();
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "引用添加失败");
    } finally { setPending(null); }
  };

  const remove = async (citationId: string) => {
    setPending(`delete:${citationId}`);
    try {
      await EnterpriseApi.deletePresentationCitation(workspaceId, entryId, citationId);
      if (preview?.citation.id === citationId) setPreview(null);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "引用删除失败");
    } finally { setPending(null); }
  };

  const openPreview = async (citationId: string) => {
    setPending(`preview:${citationId}`);
    try { setPreview(await EnterpriseApi.getPresentationCitationPreview(workspaceId, entryId, citationId)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "来源原文加载失败"); }
    finally { setPending(null); }
  };

  return <>
    <button type="button" onClick={() => setOpen(true)} className="fixed bottom-44 right-5 z-40 inline-flex h-11 items-center gap-2 rounded-full border border-[#D9DCE3] bg-white px-4 text-sm font-medium text-[#344054] shadow-lg xl:bottom-5 xl:right-[635px]">
      <FileSearch className="h-4 w-4" />本页来源
      {invalidCount > 0 && <span className="rounded-full bg-[#D92D20] px-1.5 text-[10px] text-white">{invalidCount}</span>}
    </button>
    {open && <aside className="fixed inset-y-3 right-3 z-[82] flex w-[min(440px,calc(100vw-24px))] flex-col overflow-hidden rounded-2xl border border-[#E3E4EA] bg-white shadow-2xl">
      <header className="flex items-center justify-between border-b border-[#EAECF0] px-4 py-3">
        <div><h2 className="text-sm font-semibold text-[#101828]">第 {currentSlideIndex + 1} 页引用来源</h2><p className="mt-0.5 text-xs text-[#667085]">全稿 {summary?.valid_citations ?? 0} 条有效，{summary?.invalid_citations ?? 0} 条待修复</p></div>
        <button type="button" onClick={() => setOpen(false)} className="rounded-full p-2 hover:bg-[#F2F4F7]"><X className="h-4 w-4" /></button>
      </header>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        {error && <p className="rounded-lg bg-[#FEF2F2] p-2 text-xs text-[#B42318]">{error}</p>}
        {currentCitations.length === 0 && <p className="rounded-xl bg-[#F8F9FC] p-4 text-center text-xs text-[#667085]">当前页暂无引用，可从下方企业资料中添加。</p>}
        {currentCitations.map((item) => <article key={item.id} className="rounded-xl border border-[#EAECF0] p-3">
          <div className="flex items-start gap-2">{item.status === "valid" ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#039855]" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#D92D20]" />}<div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-[#101828]">{item.source_name || item.source_id}</p><p className="mt-1 text-xs text-[#667085]">{item.source_category || item.source_type} · 引用版本 {item.source_version || "-"}</p><p className={`mt-1 text-xs ${item.status === "valid" ? "text-[#027A48]" : "text-[#B42318]"}`}>{item.status_message}</p>{item.excerpt && <p className="mt-2 line-clamp-3 rounded-lg bg-[#F8F9FC] p-2 text-xs leading-5 text-[#475467]">{item.excerpt}</p>}</div></div>
          <div className="mt-3 flex gap-2"><button type="button" onClick={() => void openPreview(item.id)} disabled={pending !== null || !item.source_available} className="rounded-lg border border-[#D9DCE3] px-2 py-1.5 text-xs disabled:opacity-40">查看原文</button>{item.status !== "valid" && <button type="button" onClick={() => setQuery(item.source_name || "")} className="rounded-lg bg-[#FFF4E5] px-2 py-1.5 text-xs text-[#B54708]">搜索新版本</button>}{canEdit && <button type="button" onClick={() => void remove(item.id)} disabled={pending !== null} className="ml-auto rounded-lg p-1.5 text-[#B42318] hover:bg-[#FEF2F2] disabled:opacity-40">{pending === `delete:${item.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}</button>}</div>
        </article>)}
        {preview && <section className="rounded-xl border border-[#CBC7FF] bg-[#F8F7FF] p-3"><div className="flex items-start justify-between gap-2"><div><p className="text-xs font-semibold text-[#4238CA]">来源原文{preview.heading ? ` · ${preview.heading}` : ""}</p><p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-[#344054]">{preview.content || "当前来源无法预览"}</p></div><button type="button" onClick={() => setPreview(null)}><X className="h-3.5 w-3.5" /></button></div></section>}
        {canEdit && <form onSubmit={search} className="rounded-xl border border-[#EAECF0] p-3"><p className="mb-2 text-xs font-medium text-[#344054]">从企业资料补充或替换引用</p><div className="flex gap-2"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="输入事实、指标或资料名" className="h-9 min-w-0 flex-1 rounded-lg border border-[#D9DCE3] px-3 text-xs" /><button disabled={!query.trim() || pending !== null} className="flex h-9 items-center gap-1 rounded-lg bg-[#635BFF] px-3 text-xs text-white disabled:opacity-40">{pending === "search" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}检索</button></div></form>}
        {results.map((item) => <article key={item.chunk_id} className="rounded-xl border border-[#EAECF0] p-3"><p className="text-sm font-medium text-[#101828]">{item.logical_name}</p><p className="mt-1 text-xs text-[#667085]">{item.heading || item.category} · v{item.document_version}</p><p className="mt-2 line-clamp-4 text-xs leading-5 text-[#475467]">{item.excerpt}</p><button type="button" onClick={() => void add(item)} disabled={!currentSlideId || pending !== null} className="mt-3 flex items-center gap-1 rounded-lg bg-[#F2F1FF] px-2 py-1.5 text-xs text-[#4238CA] disabled:opacity-40">{pending === `add:${item.chunk_id}` ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}引用到当前页</button></article>)}
      </div>
    </aside>}
  </>;
}
