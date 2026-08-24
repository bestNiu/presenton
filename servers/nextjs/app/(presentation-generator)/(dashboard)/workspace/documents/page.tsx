"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { ArrowLeft, Download, Eye, FileSearch, Loader2, RefreshCw, Sparkles, Upload } from "lucide-react";

import {
  EnterpriseApi,
  type ConfidentialityLevel,
  type EnterpriseDocumentResponse,
  type EnterpriseDocumentDetailResponse,
  type EnterpriseKnowledgeOutlineResponse,
  type EnterpriseKnowledgeSearchItemResponse,
  type PresentationEntryResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";
import { useEnterpriseWorkspace } from "../components/EnterpriseWorkspaceShell";
import ResourceDetailDrawer from "../components/ResourceDetailDrawer";

const parseLabel: Record<EnterpriseDocumentResponse["parse_status"], string> = {
  queued: "等待解析",
  parsing: "解析中",
  ready: "可检索",
  error: "解析失败",
};

export default function EnterpriseDocumentCenterPage() {
  const {
    workspaces,
    activeWorkspaceId: workspaceId,
    setActiveWorkspaceId: setWorkspaceId,
  } = useEnterpriseWorkspace();
  const [documents, setDocuments] = useState<EnterpriseDocumentResponse[]>([]);
  const [documentVersions, setDocumentVersions] = useState<EnterpriseDocumentResponse[]>([]);
  const [documentDetail, setDocumentDetail] = useState<EnterpriseDocumentDetailResponse | null>(null);
  const [presentations, setPresentations] = useState<PresentationEntryResponse[]>([]);
  const [targetEntryId, setTargetEntryId] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [logicalName, setLogicalName] = useState("");
  const [category, setCategory] = useState("通用资料");
  const [confidentiality, setConfidentiality] = useState<ConfidentialityLevel>("L2");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<EnterpriseKnowledgeSearchItemResponse[]>([]);
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("管理层");
  const [nSlides, setNSlides] = useState(8);
  const [outline, setOutline] = useState<EnterpriseKnowledgeOutlineResponse | null>(null);
  const [generatedPresentationId, setGeneratedPresentationId] = useState("");
  const [pending, setPending] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    if (!workspaceId) return;
    setPending("load");
    try {
      const [documentRows, presentationRows] = await Promise.all([
        EnterpriseApi.getDocuments(workspaceId, true),
        EnterpriseApi.getPresentations(workspaceId),
      ]);
      setDocumentVersions(documentRows);
      setDocuments(documentRows.filter((item) => item.is_latest));
      setPresentations(presentationRows);
      setTargetEntryId((current) => presentationRows.some((item) => item.id === current) ? current : presentationRows[0]?.id || "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "文档加载失败");
    } finally {
      setPending("");
    }
  }, [workspaceId]);

  useEffect(() => { void loadDocuments(); }, [loadDocuments]);
  useEffect(() => {
    if (!documents.some((item) => ["queued", "parsing"].includes(item.parse_status))) return;
    const timer = window.setInterval(() => void loadDocuments(), 3000);
    return () => window.clearInterval(timer);
  }, [documents, loadDocuments]);

  const upload = async (event: FormEvent) => {
    event.preventDefault();
    if (!workspaceId || !file) return;
    setPending("upload"); setError(null);
    try {
      await EnterpriseApi.uploadDocument(workspaceId, file, { logicalName: logicalName.trim() || file.name.replace(/\.[^.]+$/, ""), category, confidentiality });
      setFile(null); setLogicalName("");
      await loadDocuments();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "上传失败");
    } finally { setPending(""); }
  };

  const search = async (event: FormEvent) => {
    event.preventDefault();
    if (!workspaceId || !query.trim()) return;
    setPending("search"); setError(null);
    try { setResults(await EnterpriseApi.searchKnowledge(workspaceId, query.trim(), selected)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "检索失败"); }
    finally { setPending(""); }
  };

  const generateOutline = async (event: FormEvent) => {
    event.preventDefault();
    if (!workspaceId || !topic.trim()) return;
    setPending("outline"); setError(null); setOutline(null);
    try {
      const created = await EnterpriseApi.createKnowledgePresentation(workspaceId, { topic: topic.trim(), query: query.trim() || topic.trim(), audience, nSlides, documentIds: selected }, crypto.randomUUID());
      setGeneratedPresentationId(created.presentation_id);
      let current = created.outline;
      for (let attempt = 0; attempt < 30 && ["queued", "generating"].includes(current.status); attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        current = await EnterpriseApi.getKnowledgeOutline(created.outline.id);
      }
      setOutline(current);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "大纲生成失败"); }
    finally { setPending(""); }
  };

  const applyOutline = async () => {
    if (!outline || !workspaceId || !targetEntryId) return;
    setPending("apply"); setError(null);
    try {
      const applied = await EnterpriseApi.applyKnowledgeOutline(outline.id, workspaceId, targetEntryId);
      setOutline(applied);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "大纲应用失败"); }
    finally { setPending(""); }
  };

  const inspectDocument = async (documentId: string) => {
    setPending(`detail:${documentId}`);
    setError(null);
    try {
      setDocumentDetail(await EnterpriseApi.getDocumentDetail(documentId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "文档详情加载失败");
    } finally {
      setPending("");
    }
  };

  return <><main className="min-h-screen bg-[#FBFBFD] px-5 py-8 sm:px-8">
    <div className="mx-auto max-w-[1280px]">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-[#E8E8ED] pb-6">
        <div><Link href="/workspace" className="mb-3 inline-flex items-center gap-1 text-sm text-[#667085]"><ArrowLeft className="h-4 w-4" />返回工作空间</Link><h1 className="text-3xl font-semibold text-[#17171B]">企业文档与知识中心</h1><p className="mt-2 text-sm text-[#667085]">统一管理资料版本、检索可信内容，并生成带来源的大纲。</p></div>
        <div className="flex gap-2"><select value={workspaceId} onChange={(event) => setWorkspaceId(event.target.value)} className="h-10 rounded-lg border bg-white px-3 text-sm">{workspaces.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><button onClick={() => void loadDocuments()} className="inline-flex h-10 items-center gap-2 rounded-lg border bg-white px-3 text-sm"><RefreshCw className="h-4 w-4" />刷新</button></div>
      </header>
      {error && <div className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="rounded-2xl border border-[#E3E4EA] bg-white p-5"><h2 className="font-semibold">资料库</h2>
          <form onSubmit={upload} className="mt-4 grid gap-3 rounded-xl bg-[#F8F9FC] p-4 sm:grid-cols-2">
            <input type="file" onChange={(event) => setFile(event.target.files?.[0] || null)} className="text-sm" />
            <input value={logicalName} onChange={(event) => setLogicalName(event.target.value)} placeholder="逻辑资料名称（同名形成新版本）" className="h-10 rounded-lg border px-3 text-sm" />
            <input value={category} onChange={(event) => setCategory(event.target.value)} placeholder="分类" className="h-10 rounded-lg border px-3 text-sm" />
            <div className="flex gap-2"><select value={confidentiality} onChange={(event) => setConfidentiality(event.target.value as ConfidentialityLevel)} className="h-10 flex-1 rounded-lg border bg-white px-3 text-sm"><option value="L1">L1</option><option value="L2">L2</option><option value="L3">L3</option><option value="L4">L4</option></select><button disabled={!file || pending === "upload"} className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#635BFF] px-4 text-sm text-white disabled:opacity-50">{pending === "upload" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}上传</button></div>
          </form>
          <div className="mt-4 space-y-2">{documents.map((item) => <div key={item.id} className="flex items-center gap-3 rounded-xl border p-3"><input type="checkbox" aria-label={`选择资料：${item.logical_name}`} checked={selected.includes(item.id)} disabled={item.parse_status !== "ready"} onChange={(event) => setSelected((current) => event.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id))} /><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{item.logical_name} <span className="text-xs text-[#98A2B3]">v{item.version_no}</span></p><p className="mt-1 text-xs text-[#667085]">{item.category} · {parseLabel[item.parse_status]} · {Math.ceil(item.size_bytes / 1024)} KB</p>{item.parse_error && <p className="mt-1 text-xs text-red-600">{item.parse_error}</p>}</div><button type="button" disabled={pending === `detail:${item.id}`} onClick={() => void inspectDocument(item.id)} className="inline-flex items-center gap-1 rounded-lg border border-[#D0D5DD] px-2.5 py-1.5 text-xs text-[#344054]"><Eye className="h-3.5 w-3.5" />详情</button>{item.parse_status === "error" && <button type="button" onClick={() => void EnterpriseApi.retryDocumentParse(item.id).then(loadDocuments)} className="text-xs text-[#635BFF]">重试</button>}</div>)}{!documents.length && <p className="py-10 text-center text-sm text-[#98A2B3]">暂无资料</p>}</div>
        </section>
        <div className="space-y-6">
          <section className="rounded-2xl border bg-white p-5"><h2 className="flex items-center gap-2 font-semibold"><FileSearch className="h-5 w-5 text-[#087BCB]" />知识检索</h2><form onSubmit={search} className="mt-4 flex gap-2"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索事实、数据或结论" className="h-10 min-w-0 flex-1 rounded-lg border px-3 text-sm" /><button disabled={!query.trim()} className="rounded-lg bg-[#087BCB] px-4 text-sm text-white">检索</button></form><div className="mt-3 space-y-2">{results.map((item) => <div key={item.chunk_id} className="rounded-lg bg-[#F8F9FC] p-3"><div className="flex justify-between gap-3"><p className="text-sm font-medium">{item.logical_name} · {item.heading || "正文"}</p><span className="text-xs text-[#087BCB]">{item.score}</span></div><p className="mt-1 line-clamp-3 text-xs leading-5 text-[#667085]">{item.excerpt}</p><p className="mt-1 text-[11px] text-[#98A2B3]">v{item.document_version} · {item.citation.locator}</p></div>)}</div></section>
          <section className="rounded-2xl border bg-white p-5"><h2 className="flex items-center gap-2 font-semibold"><Sparkles className="h-5 w-5 text-[#635BFF]" />资料驱动大纲</h2><form onSubmit={generateOutline} className="mt-4 grid gap-3"><input value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="汇报主题" className="h-10 rounded-lg border px-3 text-sm" /><div className="grid grid-cols-[1fr_100px] gap-2"><input value={audience} onChange={(event) => setAudience(event.target.value)} placeholder="受众" className="h-10 rounded-lg border px-3 text-sm" /><input type="number" min={1} max={30} value={nSlides} onChange={(event) => setNSlides(Number(event.target.value))} className="h-10 rounded-lg border px-3 text-sm" /></div><button disabled={!topic.trim() || !selected.length || pending === "outline"} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-[#635BFF] text-sm text-white disabled:opacity-50">{pending === "outline" && <Loader2 className="h-4 w-4 animate-spin" />}创建资料驱动文稿</button></form>{outline && <div className="mt-4"><p className={`text-sm ${outline.status === "error" ? "text-red-600" : "text-[#475467]"}`}>{outline.status === "ready" ? `已生成 ${outline.outline.slides?.length || 0} 页，引用 ${outline.context_manifest.length} 个知识切片` : outline.error || "生成中"}</p><ol className="mt-3 space-y-2">{outline.outline.slides?.map((slide, index) => <li key={index} className="rounded-lg border p-3 text-sm"><p className="whitespace-pre-wrap">{slide.content}</p><p className="mt-2 text-xs text-[#635BFF]">来源：{slide.citation_refs.join("、")}</p></li>)}</ol>{outline.status === "ready" && <div className="mt-4 flex gap-2">{generatedPresentationId && <Link href={`/outline?id=${encodeURIComponent(generatedPresentationId)}&type=standard`} className="inline-flex h-10 items-center rounded-lg bg-[#17171B] px-4 text-sm text-white">确认大纲并生成页面</Link>}<select value={targetEntryId} onChange={(event) => setTargetEntryId(event.target.value)} className="h-10 min-w-0 flex-1 rounded-lg border bg-white px-3 text-sm"><option value="">或应用到已有文稿</option>{presentations.map((item) => <option key={item.id} value={item.id}>{item.title || "未命名文稿"}</option>)}</select><button type="button" onClick={() => void applyOutline()} disabled={!targetEntryId || pending === "apply"} className="rounded-lg border border-[#635BFF] px-4 text-sm text-[#635BFF] disabled:opacity-50">应用</button></div>}</div>}</section>
        </div>
      </div>
    </div>
  </main>
  <ResourceDetailDrawer
    open={Boolean(documentDetail)}
    eyebrow="企业文档详情"
    title={documentDetail?.logical_name || ""}
    description={documentDetail?.file_name}
    status={documentDetail ? `${parseLabel[documentDetail.parse_status]} · ${documentDetail.authorization_status}` : ""}
    onClose={() => setDocumentDetail(null)}
    fields={documentDetail ? [
      { label: "分类与密级", value: `${documentDetail.category} · ${documentDetail.confidentiality}` },
      { label: "文件大小", value: `${Math.ceil(documentDetail.size_bytes / 1024)} KB` },
      { label: "内容指纹", value: <span className="font-mono text-xs">{documentDetail.sha256}</span> },
      { label: "有效期限", value: documentDetail.expires_at ? new Date(documentDetail.expires_at).toLocaleString("zh-CN") : "长期有效" },
      { label: "解析更新时间", value: new Date(documentDetail.updated_at).toLocaleString("zh-CN") },
      { label: "版本组", value: <span className="font-mono text-xs">{documentDetail.version_group_id}</span> },
    ] : []}
    versions={documentDetail ? documentVersions.filter((item) => item.version_group_id === documentDetail.version_group_id).sort((a, b) => b.version_no - a.version_no).map((item) => ({ id: item.id, label: `v${item.version_no} · ${parseLabel[item.parse_status]}`, detail: new Date(item.created_at).toLocaleString("zh-CN"), current: item.is_latest })) : []}
    governanceNote="只有最新、解析成功且授权未撤销的版本可进入知识检索与 PPT 生成；历史版本保留用于审计追溯。"
    actions={documentDetail && <a href={EnterpriseApi.getDocumentDownloadUrl(documentDetail.id)} className="inline-flex h-9 items-center gap-2 rounded-lg bg-[#635BFF] px-4 text-sm text-white"><Download className="h-4 w-4" />下载原文件</a>}
  >
    {documentDetail?.extracted_text && <section><h3 className="text-sm font-semibold text-[#101828]">解析内容预览</h3><p className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-xl bg-[#F8F9FC] p-3 text-xs leading-5 text-[#475467]">{documentDetail.extracted_text.slice(0, 3000)}</p></section>}
  </ResourceDetailDrawer>
  </>;
}
