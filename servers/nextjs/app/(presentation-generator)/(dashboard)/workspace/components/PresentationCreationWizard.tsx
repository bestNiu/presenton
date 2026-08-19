"use client";

import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  FileText,
  LayoutTemplate,
  Loader2,
  PlusSquare,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";

type CreationMode = "topic" | "document" | "template" | "blank" | "import";

interface FolderOption {
  id: string;
  name: string;
  depth: number;
}

interface PresentationCreationWizardProps {
  open: boolean;
  workspaceId: string;
  folders: FolderOption[];
  defaultFolderId?: string;
  onClose: () => void;
  onCreateBlank: (folderId?: string) => Promise<void>;
}

const modes: Array<{ mode: CreationMode; label: string; detail: string; icon: typeof Sparkles }> = [
  { mode: "topic", label: "主题生成", detail: "输入主题、受众与表达目标，由 AI 生成完整文稿", icon: Sparkles },
  { mode: "document", label: "企业资料", detail: "上传文档、表格或已有材料，基于资料生成", icon: FileText },
  { mode: "template", label: "企业模板", detail: "从指定设计模板开始生成内容", icon: LayoutTemplate },
  { mode: "blank", label: "空白文稿", detail: "创建空白画布，在编辑器中自由编排", icon: PlusSquare },
  { mode: "import", label: "导入文件", detail: "导入已有 PPT、PDF 或办公文档继续加工", icon: Upload },
];

const templates = [
  { value: "executive", label: "管理层汇报", detail: "克制、清晰，适合经营与决策汇报" },
  { value: "momentum", label: "业务提案", detail: "强调叙事和关键结论，适合方案与路演" },
  { value: "dynamic", label: "培训课程", detail: "层次活跃，适合教学、宣贯与工作坊" },
];

export default function PresentationCreationWizard({
  open,
  workspaceId,
  folders,
  defaultFolderId,
  onClose,
  onCreateBlank,
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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedMode = useMemo(() => modes.find((item) => item.mode === mode) || modes[0], [mode]);
  if (!open) return null;

  const close = () => {
    if (busy) return;
    setStep(1);
    setError(null);
    onClose();
  };

  const canContinue = step !== 2 || mode === "blank" || Boolean(topic.trim()) || mode === "document" || mode === "import";

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const targetFolder = folderId === "root" ? undefined : folderId;
      if (mode === "blank") {
        await onCreateBlank(targetFolder);
        return;
      }
      const params = new URLSearchParams({
        entry: mode === "template" ? "template" : mode === "document" || mode === "import" ? "document" : "topic",
        workspace_id: workspaceId,
        template,
        slides,
        language,
        tone,
      });
      if (targetFolder) params.set("folder_id", targetFolder);
      if (topic.trim()) params.set("prompt", `${topic.trim()}${audience.trim() ? `\n目标受众：${audience.trim()}` : ""}`);
      if (mode === "import") params.set("import", "true");
      router.push(`/upload?${params.toString()}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "创建文稿失败，请稍后重试");
      setBusy(false);
    }
  };

  return <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-labelledby="creation-wizard-title">
    <div className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
      <header className="flex items-start justify-between border-b border-[#EAECF0] px-6 py-5">
        <div><p className="text-xs font-semibold text-[#635BFF]">通用 PPT 创建</p><h2 id="creation-wizard-title" className="mt-1 text-xl font-semibold text-[#101828]">{["选择创建方式", "配置内容", "选择设计", "确认并创建"][step - 1]}</h2></div>
        <button type="button" onClick={close} aria-label="关闭创建向导" className="rounded-lg p-1.5 text-[#667085] hover:bg-[#F2F4F7]"><X className="h-5 w-5" /></button>
      </header>
      <div className="grid grid-cols-4 border-b border-[#EAECF0] bg-[#F8F9FC] px-6 py-3">{["创建方式", "内容配置", "设计方案", "确认创建"].map((label, index) => <div key={label} className="flex items-center gap-2 text-xs"><span className={`flex h-6 w-6 items-center justify-center rounded-full font-medium ${index + 1 <= step ? "bg-[#635BFF] text-white" : "bg-[#E4E7EC] text-[#667085]"}`}>{index + 1 < step ? <Check className="h-3.5 w-3.5" /> : index + 1}</span><span className={index + 1 <= step ? "font-medium text-[#344054]" : "text-[#98A2B3]"}>{label}</span></div>)}</div>
      <div className="min-h-0 flex-1 overflow-y-auto p-6">
        {step === 1 && <div className="grid gap-3 sm:grid-cols-2">{modes.map((item) => { const Icon = item.icon; return <button type="button" key={item.mode} onClick={() => setMode(item.mode)} className={`flex items-start gap-3 rounded-xl border p-4 text-left transition ${mode === item.mode ? "border-[#8B7DFF] bg-[#F5F3FF] ring-2 ring-[#E4E1FF]" : "border-[#E4E7EC] hover:border-[#C7C2FF]"}`}><span className="rounded-lg bg-white p-2 text-[#635BFF]"><Icon className="h-5 w-5" /></span><span><span className="block text-sm font-semibold text-[#101828]">{item.label}</span><span className="mt-1 block text-xs leading-5 text-[#667085]">{item.detail}</span></span></button>; })}</div>}
        {step === 2 && <div className="mx-auto max-w-2xl space-y-4"><div className="rounded-xl bg-[#F5F3FF] p-4 text-sm text-[#4238CA]">当前方式：{selectedMode.label}{(mode === "document" || mode === "import") && "。文件将在下一页面上传并解析。"}</div>{mode !== "blank" && <><label className="block text-sm font-medium text-[#344054]">{mode === "document" || mode === "import" ? "生成目标或补充说明" : "文稿主题"}<textarea autoFocus value={topic} onChange={(event) => setTopic(event.target.value)} rows={4} placeholder={mode === "document" || mode === "import" ? "例如：提炼资料中的关键结论，形成面向管理层的决策汇报" : "例如：2026 年上半年经营复盘与下半年增长计划"} className="mt-2 w-full rounded-xl border border-[#D0D5DD] p-3 text-sm font-normal outline-none focus:border-[#8B7DFF]" /></label><label className="block text-sm font-medium text-[#344054]">目标受众<input value={audience} onChange={(event) => setAudience(event.target.value)} placeholder="例如：公司管理层、客户评审委员会、新员工" className="mt-2 h-10 w-full rounded-lg border border-[#D0D5DD] px-3 text-sm font-normal" /></label><div className="grid gap-3 sm:grid-cols-3"><label className="text-sm font-medium text-[#344054]">页数<input type="number" min="3" max="50" value={slides} onChange={(event) => setSlides(event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-[#D0D5DD] px-3 font-normal" /></label><label className="text-sm font-medium text-[#344054]">语言<select value={language} onChange={(event) => setLanguage(event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-[#D0D5DD] bg-white px-2 font-normal"><option value="Chinese (Simplified - 中文, 汉语)">简体中文</option><option value="English">English</option><option value="Auto (English)">自动识别</option></select></label><label className="text-sm font-medium text-[#344054]">语气<select value={tone} onChange={(event) => setTone(event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-[#D0D5DD] bg-white px-2 font-normal"><option value="professional">专业正式</option><option value="educational">教学讲解</option><option value="sales_pitch">销售提案</option><option value="casual">轻松交流</option></select></label></div></>}</div>}
        {step === 3 && <div className="mx-auto max-w-2xl"><p className="text-sm text-[#667085]">选择起始设计，后续仍可在大纲和编辑器中调整。</p><div className="mt-4 grid gap-3">{templates.map((item) => <button type="button" key={item.value} onClick={() => setTemplate(item.value)} className={`rounded-xl border p-4 text-left ${template === item.value ? "border-[#8B7DFF] bg-[#F5F3FF]" : "border-[#E4E7EC]"}`}><span className="text-sm font-semibold text-[#101828]">{item.label}</span><span className="mt-1 block text-xs text-[#667085]">{item.detail}</span></button>)}</div></div>}
        {step === 4 && <div className="mx-auto max-w-2xl space-y-4"><div className="rounded-2xl border border-[#E4E7EC] p-5"><h3 className="font-semibold text-[#101828]">创建摘要</h3><dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-xs text-[#98A2B3]">创建方式</dt><dd className="mt-1 text-[#344054]">{selectedMode.label}</dd></div><div><dt className="text-xs text-[#98A2B3]">设计方案</dt><dd className="mt-1 text-[#344054]">{templates.find((item) => item.value === template)?.label}</dd></div><div><dt className="text-xs text-[#98A2B3]">文稿规格</dt><dd className="mt-1 text-[#344054]">{mode === "blank" ? "空白画布" : `${slides} 页 · ${language.startsWith("Chinese") ? "简体中文" : language}`}</dd></div><div><dt className="text-xs text-[#98A2B3]">保存位置</dt><dd className="mt-1 text-[#344054]">{folders.find((item) => item.id === folderId)?.name || "根目录"}</dd></div></dl>{topic.trim() && <div className="mt-4 border-t border-[#EAECF0] pt-4"><p className="text-xs text-[#98A2B3]">主题与目标</p><p className="mt-1 whitespace-pre-wrap text-sm text-[#344054]">{topic.trim()}</p></div>}</div><label className="block text-sm font-medium text-[#344054]">创建到文件夹<select value={folderId} onChange={(event) => setFolderId(event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-[#D0D5DD] bg-white px-3 font-normal"><option value="root">根目录</option>{folders.map((folder) => <option key={folder.id} value={folder.id}>{"　".repeat(folder.depth)}{folder.name}</option>)}</select></label><p className="rounded-xl bg-[#F8F9FC] p-3 text-xs leading-5 text-[#667085]">{mode === "blank" ? "确认后立即创建空白文稿并进入编辑器。" : "确认后进入资料与生成配置页；文档类创建可继续上传企业资料，生成任务支持刷新后恢复。"}</p></div>}
        {error && <p role="alert" className="mx-auto mt-4 max-w-2xl rounded-xl bg-[#FEF2F2] p-3 text-sm text-[#B42318]">{error}</p>}
      </div>
      <footer className="flex items-center justify-between border-t border-[#EAECF0] px-6 py-4"><button type="button" disabled={busy} onClick={step === 1 ? close : () => setStep((current) => current - 1)} className="inline-flex h-10 items-center gap-2 rounded-lg border border-[#D0D5DD] px-4 text-sm text-[#344054] disabled:opacity-40"><ArrowLeft className="h-4 w-4" />{step === 1 ? "取消" : "上一步"}</button>{step < 4 ? <button type="button" disabled={!canContinue} onClick={() => setStep((current) => current + 1)} className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#635BFF] px-4 text-sm font-medium text-white disabled:opacity-40">下一步<ArrowRight className="h-4 w-4" /></button> : <button type="button" disabled={busy} onClick={() => void start()} className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#635BFF] px-5 text-sm font-medium text-white disabled:opacity-40">{busy && <Loader2 className="h-4 w-4 animate-spin" />}确认并创建</button>}</footer>
    </div>
  </div>;
}
