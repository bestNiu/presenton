"use client";

import { useRouter } from "next/navigation";
import {
  ArrowLeft, ArrowRight, Check, FileText, LayoutTemplate, Loader2,
  PlusSquare, RefreshCw, Sparkles, Upload, X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  EnterpriseApi,
  type EnterpriseDocumentResponse,
  type TemplatePublicationResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";

type CreationMode = "topic" | "document" | "template" | "blank" | "import";
interface FolderOption { id: string; name: string; depth: number }
interface PresentationCreationWizardProps {
  open: boolean;
  workspaceId: string;
  folders: FolderOption[];
  defaultFolderId?: string;
  onClose: () => void;
  onCreateBlank: (folderId?: string) => Promise<void>;
}
interface TemplateOption {
  value: string;
  label: string;
  detail: string;
  previewUrl?: string;
  enterprise: boolean;
}

const modes: Array<{ mode: CreationMode; label: string; detail: string; icon: typeof Sparkles }> = [
  { mode: "topic", label: "主题生成", detail: "输入主题、受众与表达目标，由 AI 生成完整文稿", icon: Sparkles },
  { mode: "document", label: "企业资料", detail: "选择知识库中的已授权资料，直接生成可追溯文稿", icon: FileText },
  { mode: "template", label: "企业模板", detail: "从已发布的企业模板开始生成内容", icon: LayoutTemplate },
  { mode: "blank", label: "空白文稿", detail: "创建空白画布，在编辑器中自由编排", icon: PlusSquare },
  { mode: "import", label: "导入文件", detail: "导入已有 PPT、PDF 或办公文档继续加工", icon: Upload },
];
const fallbackTemplates: TemplateOption[] = [
  { value: "executive", label: "管理层汇报", detail: "克制、清晰，适合经营与决策汇报", enterprise: false },
  { value: "momentum", label: "业务提案", detail: "强调叙事和关键结论，适合方案与路演", enterprise: false },
  { value: "dynamic", label: "培训课程", detail: "层次活跃，适合教学、宣贯与工作坊", enterprise: false },
];
const taskStorageKey = "enterprise.generationTasks";

function rememberGenerationTask(task: Record<string, string>) {
  try {
    const parsed = JSON.parse(localStorage.getItem(taskStorageKey) || "[]");
    const tasks = Array.isArray(parsed) ? parsed : [];
    localStorage.setItem(taskStorageKey, JSON.stringify([
      task,
      ...tasks.filter((item) => item?.outlineId !== task.outlineId),
    ].slice(0, 20)));
  } catch {
    localStorage.setItem(taskStorageKey, JSON.stringify([task]));
  }
}

export default function PresentationCreationWizard({
  open, workspaceId, folders, defaultFolderId, onClose, onCreateBlank,
}: PresentationCreationWizardProps) {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [mode, setMode] = useState<CreationMode>("topic");
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("");
  const [slides, setSlides] = useState("12");
  const [language, setLanguage] = useState("Chinese (Simplified - 中文, 汉语)");
  const [tone, setTone] = useState("professional");
  const [template, setTemplate] = useState("executive");
  const [folderId, setFolderId] = useState(defaultFolderId || "root");
  const [brandRules, setBrandRules] = useState("");
  const [documents, setDocuments] = useState<EnterpriseDocumentResponse[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [publishedTemplates, setPublishedTemplates] = useState<TemplatePublicationResponse[]>([]);
  const [resourcesLoading, setResourcesLoading] = useState(false);
  const [resourceWarning, setResourceWarning] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadResources = async () => {
    if (!workspaceId) return;
    setResourcesLoading(true);
    setResourceWarning(null);
    const [documentResult, templateResult] = await Promise.allSettled([
      EnterpriseApi.getDocuments(workspaceId),
      EnterpriseApi.getPublishedTemplates(workspaceId),
    ]);
    if (documentResult.status === "fulfilled") {
      setDocuments(documentResult.value.filter((item) =>
        item.is_latest && item.parse_status === "ready" && item.authorization_status !== "revoked"
      ));
    }
    if (templateResult.status === "fulfilled") {
      setPublishedTemplates(templateResult.value);
      const preferred = templateResult.value.find((item) => item.is_default) || templateResult.value[0];
      if (preferred) setTemplate(preferred.template_id);
    }
    if (documentResult.status === "rejected" || templateResult.status === "rejected") {
      setResourceWarning("部分企业资源暂时加载失败，可重试或继续使用基础创建能力。");
    }
    setResourcesLoading(false);
  };

  useEffect(() => {
    if (open) void loadResources();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, workspaceId]);

  const templateOptions = useMemo<TemplateOption[]>(() => {
    if (!publishedTemplates.length) return fallbackTemplates;
    return publishedTemplates.map((item) => ({
      value: item.template_id,
      label: item.display_name,
      detail: item.description || `企业已发布模板 · v${item.version}`,
      previewUrl: item.preview_url || undefined,
      enterprise: true,
    }));
  }, [publishedTemplates]);
  const selectedMode = modes.find((item) => item.mode === mode) || modes[0];
  const selectedTemplate = templateOptions.find((item) => item.value === template) || templateOptions[0];
  const canContinue = step !== 2
    || mode === "blank"
    || mode === "import"
    || (Boolean(topic.trim()) && (mode !== "document" || selectedDocumentIds.length > 0));

  if (!open) return null;

  const close = () => {
    if (busy) return;
    setStep(1);
    setError(null);
    onClose();
  };
  const toggleDocument = (documentId: string) => {
    setSelectedDocumentIds((current) => current.includes(documentId)
      ? current.filter((id) => id !== documentId)
      : [...current, documentId]);
  };

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const targetFolder = folderId === "root" ? undefined : folderId;
      if (mode === "blank") {
        await onCreateBlank(targetFolder);
        return;
      }
      if (mode === "document") {
        const response = await EnterpriseApi.createKnowledgePresentation(workspaceId, {
          topic: topic.trim(),
          query: topic.trim(),
          audience: audience.trim() || undefined,
          nSlides: Number(slides),
          documentIds: selectedDocumentIds,
          instructions: brandRules.trim() || undefined,
          folderId: targetFolder,
          language: language.startsWith("Chinese") ? "Chinese" : language,
        }, crypto.randomUUID());
        const generationParams = new URLSearchParams({
          workspace_id: workspaceId,
          outline_id: response.outline.id,
          presentation_id: response.presentation_id,
          template,
        });
        const url = `/workspace/presentations/${response.presentation_entry_id}/generation?${generationParams.toString()}`;
        rememberGenerationTask({
          outlineId: response.outline.id,
          entryId: response.presentation_entry_id,
          workspaceId,
          topic: topic.trim(),
          createdAt: new Date().toISOString(),
          url,
        });
        router.push(url);
        return;
      }
      const uploadParams = new URLSearchParams({
        entry: mode === "template" ? "template" : mode === "import" ? "document" : "topic",
        workspace_id: workspaceId,
        template,
        slides,
        language,
        tone,
      });
      if (targetFolder) uploadParams.set("folder_id", targetFolder);
      if (topic.trim()) uploadParams.set("prompt", `${topic.trim()}${audience.trim() ? `\n目标受众：${audience.trim()}` : ""}`);
      if (brandRules.trim()) uploadParams.set("instructions", brandRules.trim());
      if (mode === "import") uploadParams.set("import", "true");
      router.push(`/upload?${uploadParams.toString()}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "创建文稿失败，请稍后重试");
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-labelledby="creation-wizard-title">
      <div className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <header className="flex items-start justify-between border-b border-[#EAECF0] px-6 py-5">
          <div>
            <p className="text-xs font-semibold text-[#635BFF]">通用 PPT 创建</p>
            <h2 id="creation-wizard-title" className="mt-1 text-xl font-semibold text-[#101828]">
              {["选择创建方式", "配置内容", "选择设计", "确认并创建"][step - 1]}
            </h2>
          </div>
          <button type="button" onClick={close} aria-label="关闭创建向导" className="rounded-lg p-1.5 text-[#667085] hover:bg-[#F2F4F7]"><X className="h-5 w-5" /></button>
        </header>
        <div className="grid grid-cols-4 border-b border-[#EAECF0] bg-[#F8F9FC] px-6 py-3">
          {["创建方式", "内容配置", "设计方案", "确认创建"].map((label, index) => (
            <div key={label} className="flex items-center gap-2 text-xs">
              <span className={`flex h-6 w-6 items-center justify-center rounded-full font-medium ${index + 1 <= step ? "bg-[#635BFF] text-white" : "bg-[#E4E7EC] text-[#667085]"}`}>
                {index + 1 < step ? <Check className="h-3.5 w-3.5" /> : index + 1}
              </span>
              <span className={index + 1 <= step ? "font-medium text-[#344054]" : "text-[#98A2B3]"}>{label}</span>
            </div>
          ))}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-6">
          {resourceWarning && (
            <div className="mb-4 flex items-center justify-between rounded-xl bg-[#FFFAEB] p-3 text-xs text-[#93370D]">
              <span>{resourceWarning}</span>
              <button type="button" onClick={() => void loadResources()} className="inline-flex items-center gap-1 font-medium"><RefreshCw className="h-3.5 w-3.5" />重试</button>
            </div>
          )}
          {step === 1 && (
            <div className="grid gap-3 sm:grid-cols-2">
              {modes.map((item) => {
                const Icon = item.icon;
                return (
                  <button type="button" key={item.mode} onClick={() => setMode(item.mode)} className={`flex items-start gap-3 rounded-xl border p-4 text-left transition ${mode === item.mode ? "border-[#8B7DFF] bg-[#F5F3FF] ring-2 ring-[#E4E1FF]" : "border-[#E4E7EC] hover:border-[#C7C2FF]"}`}>
                    <span className="rounded-lg bg-white p-2 text-[#635BFF]"><Icon className="h-5 w-5" /></span>
                    <span><span className="block text-sm font-semibold text-[#101828]">{item.label}</span><span className="mt-1 block text-xs leading-5 text-[#667085]">{item.detail}</span></span>
                  </button>
                );
              })}
            </div>
          )}
          {step === 2 && (
            <div className="mx-auto max-w-2xl space-y-4">
              <div className="rounded-xl bg-[#F5F3FF] p-4 text-sm text-[#4238CA]">当前方式：{selectedMode.label}{mode === "import" && "。文件将在下一页面上传并解析。"}</div>
              {mode !== "blank" && (
                <>
                  <label className="block text-sm font-medium text-[#344054]">
                    {mode === "import" ? "生成目标或补充说明" : "文稿主题"}
                    <textarea autoFocus value={topic} onChange={(event) => setTopic(event.target.value)} rows={3} placeholder={mode === "import" ? "例如：提炼材料中的关键结论，形成管理层决策汇报" : "例如：2026 年上半年经营复盘与下半年增长计划"} className="mt-2 w-full rounded-xl border border-[#D0D5DD] p-3 text-sm font-normal outline-none focus:border-[#8B7DFF]" />
                  </label>
                  {mode === "document" && (
                    <fieldset>
                      <legend className="text-sm font-medium text-[#344054]">选择企业资料 <span className="font-normal text-[#98A2B3]">（已选 {selectedDocumentIds.length} 项）</span></legend>
                      <div className="mt-2 max-h-52 space-y-2 overflow-y-auto rounded-xl border border-[#E4E7EC] p-2">
                        {resourcesLoading ? <p className="p-3 text-sm text-[#667085]">正在加载企业知识库…</p> : documents.length ? documents.map((item) => (
                          <label key={item.id} className="flex cursor-pointer items-start gap-3 rounded-lg p-3 hover:bg-[#F8F9FC]">
                            <input type="checkbox" checked={selectedDocumentIds.includes(item.id)} onChange={() => toggleDocument(item.id)} className="mt-0.5 h-4 w-4 accent-[#635BFF]" />
                            <span className="min-w-0"><span className="block truncate text-sm font-medium text-[#344054]">{item.logical_name || item.file_name}</span><span className="mt-0.5 block text-xs text-[#98A2B3]">{item.category} · v{item.version_no} · {item.confidentiality}</span></span>
                          </label>
                        )) : <p className="p-3 text-sm leading-6 text-[#667085]">暂无可用的已解析资料。请先到“文档与知识”上传并完成解析。</p>}
                      </div>
                    </fieldset>
                  )}
                  <label className="block text-sm font-medium text-[#344054]">目标受众<input value={audience} onChange={(event) => setAudience(event.target.value)} placeholder="例如：公司管理层、客户评审委员会、新员工" className="mt-2 h-10 w-full rounded-lg border border-[#D0D5DD] px-3 text-sm font-normal" /></label>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <label className="text-sm font-medium text-[#344054]">页数<input type="number" min="3" max="50" value={slides} onChange={(event) => setSlides(event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-[#D0D5DD] px-3 font-normal" /></label>
                    <label className="text-sm font-medium text-[#344054]">语言<select value={language} onChange={(event) => setLanguage(event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-[#D0D5DD] bg-white px-2 font-normal"><option value="Chinese (Simplified - 中文, 汉语)">简体中文</option><option value="English">English</option><option value="Auto (English)">自动识别</option></select></label>
                    <label className="text-sm font-medium text-[#344054]">语气<select value={tone} onChange={(event) => setTone(event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-[#D0D5DD] bg-white px-2 font-normal"><option value="professional">专业正式</option><option value="educational">教学讲解</option><option value="sales_pitch">销售提案</option><option value="casual">轻松交流</option></select></label>
                  </div>
                </>
              )}
            </div>
          )}
          {step === 3 && (
            <div className="mx-auto max-w-2xl space-y-5">
              <div>
                <p className="text-sm text-[#667085]">选择起始设计。优先展示当前工作空间已发布的企业模板。</p>
                <div className="mt-4 grid gap-3">{templateOptions.map((item) => (
                  <button type="button" key={item.value} onClick={() => setTemplate(item.value)} className={`flex items-center gap-4 rounded-xl border p-4 text-left ${template === item.value ? "border-[#8B7DFF] bg-[#F5F3FF]" : "border-[#E4E7EC]"}`}>
                    <span className="h-12 w-20 shrink-0 rounded-lg bg-gradient-to-br from-[#E4E1FF] via-white to-[#D1E9FF] bg-cover bg-center" style={item.previewUrl ? { backgroundImage: `url(${item.previewUrl})` } : undefined} />
                    <span className="min-w-0"><span className="flex items-center gap-2 text-sm font-semibold text-[#101828]">{item.label}{item.enterprise && <span className="rounded-full bg-[#ECFDF3] px-2 py-0.5 text-[10px] font-medium text-[#027A48]">企业已发布</span>}</span><span className="mt-1 block text-xs text-[#667085]">{item.detail}</span></span>
                  </button>
                ))}</div>
              </div>
              <label className="block text-sm font-medium text-[#344054]">品牌与生成约束 <span className="font-normal text-[#98A2B3]">（可选）</span><textarea value={brandRules} onChange={(event) => setBrandRules(event.target.value)} rows={4} placeholder="例如：使用公司标准蓝；禁止使用未经核验的外部数据；每页必须有结论型标题；金额统一使用万元。" className="mt-2 w-full rounded-xl border border-[#D0D5DD] p-3 text-sm font-normal outline-none focus:border-[#8B7DFF]" /></label>
            </div>
          )}
          {step === 4 && (
            <div className="mx-auto max-w-2xl space-y-4">
              <div className="rounded-2xl border border-[#E4E7EC] p-5">
                <h3 className="font-semibold text-[#101828]">创建摘要</h3>
                <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                  <div><dt className="text-xs text-[#98A2B3]">创建方式</dt><dd className="mt-1 text-[#344054]">{selectedMode.label}</dd></div>
                  <div><dt className="text-xs text-[#98A2B3]">设计方案</dt><dd className="mt-1 text-[#344054]">{selectedTemplate?.label || template}</dd></div>
                  <div><dt className="text-xs text-[#98A2B3]">文稿规格</dt><dd className="mt-1 text-[#344054]">{mode === "blank" ? "空白画布" : `${slides} 页 · ${language.startsWith("Chinese") ? "简体中文" : language}`}</dd></div>
                  <div><dt className="text-xs text-[#98A2B3]">保存位置</dt><dd className="mt-1 text-[#344054]">{folders.find((item) => item.id === folderId)?.name || "根目录"}</dd></div>
                  {mode === "document" && <div><dt className="text-xs text-[#98A2B3]">引用资料</dt><dd className="mt-1 text-[#344054]">{selectedDocumentIds.length} 份企业资料</dd></div>}
                  <div><dt className="text-xs text-[#98A2B3]">品牌约束</dt><dd className="mt-1 text-[#344054]">{brandRules.trim() ? "已配置" : "使用默认规范"}</dd></div>
                </dl>
                {topic.trim() && <div className="mt-4 border-t border-[#EAECF0] pt-4"><p className="text-xs text-[#98A2B3]">主题与目标</p><p className="mt-1 whitespace-pre-wrap text-sm text-[#344054]">{topic.trim()}</p></div>}
              </div>
              <label className="block text-sm font-medium text-[#344054]">创建到文件夹<select value={folderId} onChange={(event) => setFolderId(event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-[#D0D5DD] bg-white px-3 font-normal"><option value="root">根目录</option>{folders.map((folder) => <option key={folder.id} value={folder.id}>{"　".repeat(folder.depth)}{folder.name}</option>)}</select></label>
              <p className="rounded-xl bg-[#F8F9FC] p-3 text-xs leading-5 text-[#667085]">{mode === "blank" ? "确认后立即创建空白文稿并进入编辑器。" : mode === "document" ? "确认后将基于所选企业资料创建可追溯大纲；任务可在刷新或重新打开页面后继续恢复。" : "确认后进入生成配置页，仍可补充文件与高级参数。"}</p>
            </div>
          )}
          {error && <p role="alert" className="mx-auto mt-4 max-w-2xl rounded-xl bg-[#FEF2F2] p-3 text-sm text-[#B42318]">{error}</p>}
        </div>
        <footer className="flex items-center justify-between border-t border-[#EAECF0] px-6 py-4">
          <button type="button" disabled={busy} onClick={step === 1 ? close : () => setStep((current) => current - 1)} className="inline-flex h-10 items-center gap-2 rounded-lg border border-[#D0D5DD] px-4 text-sm text-[#344054] disabled:opacity-40"><ArrowLeft className="h-4 w-4" />{step === 1 ? "取消" : "上一步"}</button>
          {step < 4 ? <button type="button" disabled={!canContinue} onClick={() => setStep((current) => current + 1)} className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#635BFF] px-4 text-sm font-medium text-white disabled:opacity-40">下一步<ArrowRight className="h-4 w-4" /></button> : <button type="button" disabled={busy} onClick={() => void start()} className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#635BFF] px-5 text-sm font-medium text-white disabled:opacity-40">{busy && <Loader2 className="h-4 w-4 animate-spin" />}确认并创建</button>}
        </footer>
      </div>
    </div>
  );
}
