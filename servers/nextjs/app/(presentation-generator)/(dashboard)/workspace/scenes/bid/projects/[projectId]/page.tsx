"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Activity,
  ArrowLeft,
  Ban,
  CheckCircle2,
  Download,
  FilePlus2,
  FileText,
  Loader2,
  Clock3,
  Plus,
  Save,
  Target,
} from "lucide-react";

import {
  EnterpriseApi,
  type BidProjectDashboardResponse,
  type BidCollaborationResponse,
  type BidReleaseResponse,
  type BidDeliveryArtifactResponse,
  type TemplatePublicationResponse,
  type BidRequirementResponse,
  type AuditEventResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";

const statusLabel = {
  understanding: "项目理解",
  strategy_pending: "策略待确认",
  strategy_confirmed: "策略已确认",
  archived: "已归档",
};

const profileFields = [
  ["drug", "药物"],
  ["indication", "适应症"],
  ["development", "开发阶段"],
  ["design", "研究设计"],
  ["scale", "研究规模"],
  ["safety", "安全性"],
  ["testing", "检测要求"],
  ["client", "客户关注"],
  ["gaps", "信息缺口"],
] as const;

const strategyFields = [
  ["project_assessment", "项目判断"],
  ["client_concerns", "客户担忧"],
  ["solutions", "解决方案"],
  ["differentiators", "差异化优势"],
  ["commitments", "关键承诺"],
  ["joint_decisions", "需共同决策事项"],
] as const;

type FactDraft = Record<string, { value: string; source: string }>;
type StrategyDraft = Record<string, string>;

function milestoneDate(dueDate: string | null, daysBefore: number) {
  if (!dueDate) return "待设置";
  const date = new Date(`${dueDate}T12:00:00`);
  date.setDate(date.getDate() - daysBefore);
  return date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

function factDraftFromDashboard(dashboard: BidProjectDashboardResponse): FactDraft {
  return Object.fromEntries(
    profileFields.map(([key]) => {
      const fact = dashboard.profile.facts[key];
      if (fact && typeof fact === "object" && !Array.isArray(fact)) {
        const record = fact as Record<string, unknown>;
        return [key, { value: String(record.value ?? ""), source: String(record.source ?? "") }];
      }
      return [key, { value: fact == null ? "" : String(fact), source: "" }];
    })
  );
}

function strategyDraftFromDashboard(
  dashboard: BidProjectDashboardResponse
): StrategyDraft {
  return Object.fromEntries(
    strategyFields.map(([key]) => {
      const value = dashboard.strategy.elements[key];
      return [key, Array.isArray(value) ? value.join("\n") : String(value ?? "")];
    })
  );
}

function BidProjectDashboardPage() {
  const params = useParams<{ projectId: string }>();
  const [dashboard, setDashboard] = useState<BidProjectDashboardResponse | null>(null);
  const [collaboration, setCollaboration] = useState<BidCollaborationResponse>({ modules: [], commitments: [], gates: [] });
  const [releases, setReleases] = useState<BidReleaseResponse[]>([]);
  const [deliveries, setDeliveries] = useState<Record<string, BidDeliveryArtifactResponse[]>>({});
  const [templates, setTemplates] = useState<TemplatePublicationResponse[]>([]);
  const [activity, setActivity] = useState<AuditEventResponse[]>([]);
  const [templatePublicationId, setTemplatePublicationId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState("");
  const [profileDraft, setProfileDraft] = useState<FactDraft>({});
  const [conflictDraft, setConflictDraft] = useState("");
  const [strategyDraft, setStrategyDraft] = useState<StrategyDraft>({});
  const [documentDraft, setDocumentDraft] = useState({
    logical_name: "",
    category: "rfp",
    version_no: 1,
    file_ref: "",
  });
  const [requirementDraft, setRequirementDraft] = useState({
    category: "commercial",
    original_text: "",
    mandatory: true,
    source_ref: "",
  });
  const [responses, setResponses] = useState<Record<string, string>>({});
  const [moduleDrafts, setModuleDrafts] = useState<Record<string, string>>({});
  const [commitmentDraft, setCommitmentDraft] = useState({ content: "", commitment_type: "timeline", evidence_ref: "", risk_level: "medium" });
  const [issueDrafts, setIssueDrafts] = useState<Record<string, { title: string; description: string; severity: "blocking" | "warning" }>>({});
  const [resolutionDrafts, setResolutionDrafts] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    const [next, collaborationRows] = await Promise.all([EnterpriseApi.getBidProject(params.projectId), EnterpriseApi.getBidCollaboration(params.projectId)]);
    setDashboard(next);
    setProfileDraft(factDraftFromDashboard(next));
    setConflictDraft(next.profile.conflicts.map(String).join("\n"));
    setStrategyDraft(strategyDraftFromDashboard(next));
    setResponses(
      Object.fromEntries(next.requirements.map((item) => [item.id, item.response || ""]))
    );
    setCollaboration(collaborationRows);
    setModuleDrafts(Object.fromEntries(collaborationRows.modules.map((module) => [module.id, String(module.content.summary || "")])));
    const [releaseRows, templateRows, auditRows] = await Promise.all([
      EnterpriseApi.getBidReleases(params.projectId),
      EnterpriseApi.getPublishedTemplates(next.project.workspace_id),
      EnterpriseApi.getWorkspaceAuditEvents(next.project.workspace_id, 100).catch(() => []),
    ]);
    setReleases(releaseRows);
    const deliveryRows = await Promise.all(releaseRows.map((release) => EnterpriseApi.getBidDeliveries(params.projectId, release.id)));
    setDeliveries(Object.fromEntries(releaseRows.map((release, index) => [release.id, deliveryRows[index]])));
    setTemplates(templateRows);
    const relatedIds = new Set([
      next.project.id,
      ...collaborationRows.modules.map((item) => item.id),
      ...collaborationRows.commitments.map((item) => item.id),
      ...collaborationRows.gates.flatMap((item) => [item.id, ...item.issues.map((issue) => issue.id)]),
      ...releaseRows.map((item) => item.id),
    ]);
    setActivity(auditRows.filter((item) =>
      item.event_metadata.project_id === next.project.id || relatedIds.has(item.resource_id)
    ).slice(0, 20));
    setTemplatePublicationId((current) => current || templateRows.find((item) => item.scene_type === "bid")?.id || templateRows[0]?.id || "");
  }, [params.projectId]);

  useEffect(() => {
    load().catch((cause) =>
      setError(cause instanceof Error ? cause.message : "项目加载失败")
    );
  }, [load]);

  const execute = async (key: string, action: () => Promise<unknown>) => {
    setPending(key);
    setError(null);
    try {
      await action();
      await load();
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "操作失败");
      return false;
    } finally {
      setPending("");
    }
  };

  const role = dashboard?.project.current_user_role;
  const canContribute = role === "bid_manager" || role === "contributor";
  const canReview = role === "bid_manager" || role === "reviewer";
  const canConfirmStrategy = role === "bid_manager";

  const activeDocuments = useMemo(
    () => dashboard?.documents.filter((document) => document.status === "active") || [],
    [dashboard]
  );

  if (!dashboard && !error) {
    return <main className="flex min-h-screen items-center justify-center bg-[#F7F8FC]"><Loader2 className="h-7 w-7 animate-spin text-[#635BFF]" /></main>;
  }
  if (!dashboard) {
    return <main className="min-h-screen bg-[#F7F8FC] p-8"><div className="mx-auto max-w-4xl rounded-xl border border-[#FECACA] bg-white p-6 text-sm text-[#B42318]">{error}</div></main>;
  }

  const { project, profile, requirements, strategy } = dashboard;
  const mandatoryOpen = requirements.filter((item) => item.mandatory && item.status === "open");
  const modulesApproved = collaboration.modules.length > 0 && collaboration.modules.every((item) => item.status === "approved");
  const gatesPassed = collaboration.gates.length > 0 && collaboration.gates.every((item) => item.status === "passed");
  const frozenRelease = releases.some((item) => item.status === "frozen" || item.status === "archived");
  const readyDelivery = Object.values(deliveries).flat().some((item) => item.status === "ready");
  const stageItems = [
    { id: "understanding", label: "资料与理解", owner: "竞标经理", deadline: milestoneDate(project.due_date, 14), complete: activeDocuments.length > 0 && profile.status === "confirmed", detail: `${activeDocuments.length} 份资料 · 画像${profile.status === "confirmed" ? "已确认" : "待确认"}` },
    { id: "strategy", label: "策略确认", owner: "竞标经理", deadline: milestoneDate(project.due_date, 10), complete: strategy.status === "confirmed", detail: `${mandatoryOpen.length} 个必答项待处理` },
    { id: "collaboration", label: "专业协作", owner: "医学 / 运营 / 数统", deadline: milestoneDate(project.due_date, 7), complete: modulesApproved, detail: `${collaboration.modules.filter((item) => item.status === "approved").length}/${collaboration.modules.length || 3} 模块批准` },
    { id: "gates", label: "Gate 门禁", owner: "评审人", deadline: milestoneDate(project.due_date, 4), complete: gatesPassed, detail: `${collaboration.gates.filter((item) => item.status === "passed").length}/3 已通过` },
    { id: "assembly", label: "组装版本", owner: "竞标经理", deadline: milestoneDate(project.due_date, 2), complete: frozenRelease, detail: `${releases.length} 个组装版本` },
    { id: "delivery", label: "交付归档", owner: "竞标经理", deadline: milestoneDate(project.due_date, 0), complete: readyDelivery, detail: readyDelivery ? "已有可交付文件" : "等待冻结版本" },
  ];
  const stageCompletion = Math.round(stageItems.filter((item) => item.complete).length / stageItems.length * 100);
  const projectTasks = [
    ...(!activeDocuments.length ? [{ stage: "资料与理解", title: "登记至少一份有效招标或方案资料", href: "#understanding", blocking: true }] : []),
    ...(profile.status !== "confirmed" ? [{ stage: "资料与理解", title: "补全并确认项目画像", href: "#understanding", blocking: true }] : []),
    ...mandatoryOpen.slice(0, 3).map((item) => ({ stage: "策略确认", title: `响应必答项：${item.original_text}`, href: "#strategy", blocking: true })),
    ...(strategy.status !== "confirmed" ? [{ stage: "策略确认", title: "处理策略阻断项并确认策略纸", href: "#strategy", blocking: true }] : []),
    ...collaboration.modules.filter((item) => item.status !== "approved").map((item) => ({ stage: "专业协作", title: `${{ medical: "医学", operations: "运营", statistics: "数统" }[item.module_type]}模块待${item.status === "in_review" ? "审核" : "完善"}`, href: "#collaboration", blocking: false })),
    ...collaboration.gates.filter((item) => item.status !== "passed").map((item) => ({ stage: "Gate 门禁", title: `${{ gate_1: "Gate 1 专业正确性", gate_2: "Gate 2 决策逻辑", gate_3: "Gate 3 演练冻结" }[item.gate_type]}待通过`, href: "#gates", blocking: true })),
    ...(!releases.length ? [{ stage: "组装版本", title: "选择模板并生成第一版管理层摘要", href: "#assembly", blocking: false }] : []),
    ...(frozenRelease && !readyDelivery ? [{ stage: "交付归档", title: "导出受控 PPTX 或 PDF 交付件", href: "#delivery", blocking: false }] : []),
  ];

  const saveProfile = async () => {
    const facts = Object.fromEntries(
      Object.entries(profileDraft)
        .filter(([, item]) => item.value.trim())
        .map(([key, item]) => [key, { value: item.value.trim(), source: item.source.trim() || null }])
    );
    await execute("profile-save", () =>
      EnterpriseApi.updateBidProfile(project.id, {
        facts,
        conflicts: conflictDraft.split("\n").map((line) => line.trim()).filter(Boolean),
        row_version: profile.row_version,
      })
    );
  };

  const registerDocument = async (event: FormEvent) => {
    event.preventDefault();
    const succeeded = await execute("document", () =>
      EnterpriseApi.registerBidDocument(project.id, documentDraft)
    );
    if (succeeded) {
      setDocumentDraft((current) => ({ ...current, logical_name: "", file_ref: "" }));
    }
  };

  const createRequirement = async (event: FormEvent) => {
    event.preventDefault();
    const succeeded = await execute("requirement-create", () =>
      EnterpriseApi.createBidRequirement(project.id, {
        ...requirementDraft,
        source_ref: requirementDraft.source_ref || undefined,
      })
    );
    if (succeeded) {
      setRequirementDraft((current) => ({ ...current, original_text: "", source_ref: "" }));
    }
  };

  const answerRequirement = async (requirement: BidRequirementResponse) => {
    const response = responses[requirement.id]?.trim() || "";
    await execute(`requirement-${requirement.id}`, () =>
      EnterpriseApi.updateBidRequirement(project.id, requirement.id, {
        response,
        status: response ? "answered" : "open",
        owner_department: requirement.owner_department,
        target_module: requirement.target_module,
        row_version: requirement.row_version,
      })
    );
  };

  const saveStrategy = async () => {
    const elements = Object.fromEntries(
      Object.entries(strategyDraft).map(([key, value]) => [
        key,
        value.split("\n").map((line) => line.trim()).filter(Boolean),
      ])
    );
    await execute("strategy-save", () =>
      EnterpriseApi.updateBidStrategy(project.id, {
        elements,
        row_version: strategy.row_version,
      })
    );
  };

  const saveModule = async (moduleId: string, rowVersion: number) => {
    await execute(`module-${moduleId}`, () => EnterpriseApi.updateBidModule(project.id, moduleId, { summary: moduleDrafts[moduleId] || "", sources: activeDocuments.map((item) => `${item.category}:v${item.version_no}`) }, rowVersion));
  };

  const createCommitment = async (event: FormEvent) => {
    event.preventDefault();
    const succeeded = await execute("commitment-create", () => EnterpriseApi.createBidCommitment(project.id, { ...commitmentDraft, evidence_ref: commitmentDraft.evidence_ref || undefined }));
    if (succeeded) setCommitmentDraft({ content: "", commitment_type: "timeline", evidence_ref: "", risk_level: "medium" });
  };

  const downloadDelivery = async (artifactId: string) => {
    setPending(`download-${artifactId}`);
    setError(null);
    try {
      const grant = await EnterpriseApi.issueBidDownloadGrant(project.id, artifactId);
      window.location.assign(grant.download_url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "下载授权失败");
    } finally {
      setPending("");
    }
  };

  const createGateIssue = async (gate: BidCollaborationResponse["gates"][number]) => {
    const draft = issueDrafts[gate.id];
    if (!draft?.title.trim()) return;
    const succeeded = await execute(`issue-create-${gate.id}`, () =>
      EnterpriseApi.createBidGateIssue(project.id, gate.gate_type, {
        title: draft.title.trim(),
        description: draft.description.trim() || undefined,
        severity: draft.severity,
      })
    );
    if (succeeded) {
      setIssueDrafts((current) => ({ ...current, [gate.id]: { title: "", description: "", severity: "blocking" } }));
    }
  };

  const resolveGateIssue = async (issueId: string) => {
    const resolution = resolutionDrafts[issueId]?.trim();
    if (!resolution) return;
    const succeeded = await execute(`issue-resolve-${issueId}`, () =>
      EnterpriseApi.resolveBidGateIssue(project.id, issueId, resolution)
    );
    if (succeeded) {
      setResolutionDrafts((current) => ({ ...current, [issueId]: "" }));
    }
  };

  return (
    <main className="min-h-screen bg-[#F7F8FC] px-5 py-8 sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1240px]">
        <header className="rounded-2xl bg-white p-6 shadow-sm">
          <Link href={`/workspace/scenes/bid?workspace_id=${project.workspace_id}`} className="inline-flex items-center gap-1 text-sm text-[#635BFF]"><ArrowLeft className="h-4 w-4" /> 竞标工作台</Link>
          <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div><p className="text-xs font-semibold text-[#635BFF]">{project.bid_code}</p><h1 className="mt-1 font-syne text-3xl font-semibold tracking-[-0.04em] text-[#17171B]">{project.name}</h1><p className="mt-2 text-sm text-[#667085]">{project.sponsor_name || "未填写申办方"} · {project.drug_name || "药物待确认"} · {project.indication || "适应症待确认"}</p></div>
            <div className="text-right"><span className="rounded-full bg-[#F2F1FF] px-3 py-1.5 text-xs font-medium text-[#4238CA]">{statusLabel[project.status]}</span><p className="mt-2 text-xs text-[#98A2B3]">项目角色：{role}</p><p className="mt-1 inline-flex items-center gap-1 text-xs text-[#667085]"><Clock3 className="h-3.5 w-3.5" />最终截止：{project.due_date || "待设置"}</p></div>
          </div>
        </header>

        {error && <div className="mt-4 rounded-xl border border-[#FECACA] bg-[#FEF2F2] px-4 py-3 text-sm text-[#B42318]">{error}</div>}

        <nav className="sticky top-[72px] z-30 mt-5 overflow-x-auto rounded-2xl border border-[#E3E4EA] bg-white/95 p-3 shadow-sm backdrop-blur" aria-label="竞标项目六阶段导航">
          <div className="flex min-w-[1020px] items-stretch gap-2">{stageItems.map((stage, index) => <a key={stage.id} href={`#${stage.id}`} className={`min-w-0 flex-1 rounded-xl border p-3 transition hover:border-[#B9B2FF] ${stage.complete ? "border-[#ABEFC6] bg-[#ECFDF3]" : "border-[#EAECF0] bg-[#F8F9FC]"}`}><div className="flex items-center gap-2"><span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${stage.complete ? "bg-[#027A48] text-white" : "bg-white text-[#667085]"}`}>{stage.complete ? <CheckCircle2 className="h-3.5 w-3.5" /> : index + 1}</span><span className="text-xs font-semibold text-[#344054]">{stage.label}</span></div><p className="mt-2 truncate text-[10px] text-[#667085]">{stage.detail}</p><p className="mt-1 truncate text-[10px] text-[#98A2B3]">负责：{stage.owner} · 节点：{stage.deadline}</p></a>)}</div>
        </nav>

        <section className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="资料有效版本" value={String(activeDocuments.length)} detail="RFP 与方案资料影响策略门禁" />
          <Metric label="画像状态" value={profile.status === "confirmed" ? "已确认" : "待确认"} detail={`${Object.keys(profile.facts).length} 个结构化字段`} />
          <Metric label="必答覆盖率" value={`${dashboard.mandatory_requirement_coverage}%`} detail={`${requirements.filter((item) => item.mandatory).length} 个必答项`} />
          <Metric label="策略纸" value={strategy.status === "confirmed" ? "已确认" : `v${strategy.version_no} 草稿`} detail="确认后开放专业模块" />
        </section>

        <section className="mt-5 grid gap-5 lg:grid-cols-[280px_1fr]">
          <div className="rounded-2xl bg-[#17171B] p-5 text-white"><p className="text-xs text-white/60">项目阶段完成度</p><p className="mt-2 text-3xl font-semibold">{stageCompletion}%</p><div className="mt-4 h-2 overflow-hidden rounded-full bg-white/15"><div className="h-full rounded-full bg-[#8B7DFF]" style={{ width: `${stageCompletion}%` }} /></div><p className="mt-3 text-xs leading-5 text-white/60">已完成 {stageItems.filter((item) => item.complete).length}/6 个阶段，阶段状态由业务数据自动计算。</p></div>
          <div className="rounded-2xl border border-[#E3E4EA] bg-white p-5"><div className="flex items-center justify-between"><div><h2 className="font-semibold text-[#101828]">项目任务面板</h2><p className="mt-1 text-xs text-[#667085]">聚合当前阶段阻断项和下一动作，可直接跳转处理。</p></div><span className="rounded-full bg-[#F2F1FF] px-2.5 py-1 text-xs text-[#4238CA]">{projectTasks.length} 项待办</span></div>{projectTasks.length ? <div className="mt-4 grid gap-2 sm:grid-cols-2">{projectTasks.slice(0, 8).map((task, index) => <a href={task.href} key={`${task.stage}-${index}`} className="flex items-start justify-between gap-3 rounded-xl border border-[#EAECF0] p-3 hover:border-[#B9B2FF]"><div><span className="text-[10px] font-medium text-[#635BFF]">{task.stage}</span><p className="mt-1 line-clamp-2 text-xs text-[#344054]">{task.title}</p></div>{task.blocking && <span className="shrink-0 rounded-full bg-[#FEF2F2] px-2 py-1 text-[10px] text-[#B42318]">阻断</span>}</a>)}</div> : <div className="mt-4 flex items-center gap-2 rounded-xl bg-[#ECFDF3] p-4 text-sm text-[#027A48]"><CheckCircle2 className="h-4 w-4" />当前项目没有待处理任务</div>}</div>
        </section>

        <section className="mt-5 rounded-2xl border border-[#E3E4EA] bg-white p-6">
          <div className="flex items-center gap-2"><Target className="h-4 w-4 text-[#635BFF]" /><h2 className="font-semibold text-[#101828]">策略确认门禁</h2></div>
          {dashboard.strategy_blockers.length === 0 ? <div className="mt-4 flex items-center gap-2 rounded-xl bg-[#ECFDF3] p-4 text-sm text-[#027A48]"><CheckCircle2 className="h-4 w-4" /> 所有前置检查均已通过</div> : <div className="mt-4 grid gap-2">{dashboard.strategy_blockers.map((blocker) => <div key={blocker} className="flex items-start gap-2 rounded-lg bg-[#FFFAEB] px-3 py-2.5 text-sm text-[#B54708]"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{blocker}</div>)}</div>}
        </section>

        <div id="understanding" className="mt-5 scroll-mt-40 grid gap-5 lg:grid-cols-2">
          <section className="rounded-2xl border border-[#E3E4EA] bg-white p-6">
            <div className="flex items-center gap-2"><FileText className="h-4 w-4 text-[#087BCB]" /><h2 className="font-semibold text-[#101828]">项目资料</h2></div>
            {canContribute && <form onSubmit={registerDocument} className="mt-4 grid gap-2 sm:grid-cols-2"><input value={documentDraft.logical_name} onChange={(event) => setDocumentDraft({ ...documentDraft, logical_name: event.target.value })} placeholder="资料名称" className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm" /><select value={documentDraft.category} onChange={(event) => setDocumentDraft({ ...documentDraft, category: event.target.value })} className="h-10 rounded-lg border border-[#D9DCE3] bg-white px-3 text-sm"><option value="rfp">RFP</option><option value="protocol_summary">方案摘要</option><option value="protocol">完整方案</option><option value="ib">IB</option><option value="meeting_minutes">客户会议纪要</option><option value="historical_bid">历史竞标材料</option></select><input value={documentDraft.file_ref} onChange={(event) => setDocumentDraft({ ...documentDraft, file_ref: event.target.value })} placeholder="已上传文件引用" className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm" /><button disabled={pending === "document" || !documentDraft.logical_name || !documentDraft.file_ref} className="inline-flex h-10 items-center justify-center gap-1 rounded-lg bg-[#087BCB] px-3 text-sm font-medium text-white disabled:opacity-50"><FilePlus2 className="h-4 w-4" /> 登记版本</button></form>}
            <div className="mt-4 divide-y divide-[#EAECF0]">{activeDocuments.map((document) => <div key={document.id} className="flex items-center justify-between py-3 text-sm"><span className="truncate text-[#344054]">{document.logical_name}</span><span className="text-xs text-[#667085]">{document.category} · v{document.version_no}</span></div>)}{activeDocuments.length === 0 && <p className="py-6 text-center text-sm text-[#98A2B3]">尚未登记项目资料</p>}</div>
          </section>

          <section className="rounded-2xl border border-[#E3E4EA] bg-white p-6">
            <div className="flex items-center justify-between"><h2 className="font-semibold text-[#101828]">项目画像</h2><span className="text-xs text-[#667085]">版本 {profile.row_version}</span></div>
            <div className="mt-4 grid gap-3">{profileFields.map(([key, label]) => <div key={key} className="grid gap-2 sm:grid-cols-[90px_1fr_1fr] sm:items-center"><label className="text-xs font-medium text-[#475467]">{label}</label><input disabled={!canContribute} value={profileDraft[key]?.value || ""} onChange={(event) => setProfileDraft({ ...profileDraft, [key]: { ...(profileDraft[key] || { source: "" }), value: event.target.value } })} placeholder="字段值" className="h-9 rounded-lg border border-[#D9DCE3] px-3 text-sm disabled:bg-[#F8F9FC]" /><input disabled={!canContribute} value={profileDraft[key]?.source || ""} onChange={(event) => setProfileDraft({ ...profileDraft, [key]: { ...(profileDraft[key] || { value: "" }), source: event.target.value } })} placeholder="来源，如 protocol:p2" className="h-9 rounded-lg border border-[#D9DCE3] px-3 text-sm disabled:bg-[#F8F9FC]" /></div>)}</div>
            <textarea disabled={!canContribute} value={conflictDraft} onChange={(event) => setConflictDraft(event.target.value)} placeholder="未解决冲突，每行一条" rows={3} className="mt-4 w-full rounded-lg border border-[#D9DCE3] p-3 text-sm disabled:bg-[#F8F9FC]" />
            <div className="mt-3 flex justify-end gap-2">{canContribute && <button type="button" onClick={() => void saveProfile()} disabled={pending === "profile-save"} className="inline-flex h-9 items-center gap-1 rounded-lg border border-[#D9DCE3] px-3 text-sm"><Save className="h-4 w-4" /> 保存画像</button>}{canReview && profile.status !== "confirmed" && <button type="button" onClick={() => void execute("profile-confirm", () => EnterpriseApi.confirmBidProfile(project.id))} disabled={pending === "profile-confirm"} className="h-9 rounded-lg bg-[#027A48] px-3 text-sm font-medium text-white disabled:opacity-50">确认画像</button>}</div>
          </section>
        </div>

        <section id="strategy" className="mt-5 scroll-mt-40 rounded-2xl border border-[#E3E4EA] bg-white p-6">
          <div className="flex items-center justify-between"><h2 className="font-semibold text-[#101828]">需求矩阵</h2><span className="text-xs text-[#667085]">必答覆盖 {dashboard.mandatory_requirement_coverage}%</span></div>
          {canContribute && <form onSubmit={createRequirement} className="mt-4 grid gap-2 md:grid-cols-[140px_1fr_180px_auto]"><select value={requirementDraft.category} onChange={(event) => setRequirementDraft({ ...requirementDraft, category: event.target.value })} className="h-10 rounded-lg border border-[#D9DCE3] bg-white px-3 text-sm"><option value="commercial">商务</option><option value="medical">医学</option><option value="operations">运营</option><option value="statistics">数统</option><option value="delivery">交付</option></select><input value={requirementDraft.original_text} onChange={(event) => setRequirementDraft({ ...requirementDraft, original_text: event.target.value })} placeholder="客户要求原文" className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm" /><input value={requirementDraft.source_ref} onChange={(event) => setRequirementDraft({ ...requirementDraft, source_ref: event.target.value })} placeholder="来源，如 rfp:p8" className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm" /><button disabled={pending === "requirement-create" || !requirementDraft.original_text.trim()} className="inline-flex h-10 items-center justify-center gap-1 rounded-lg bg-[#635BFF] px-3 text-sm font-medium text-white disabled:opacity-50"><Plus className="h-4 w-4" /> 添加</button></form>}
          <div className="mt-4 grid gap-3">{requirements.map((item) => <article key={item.id} className="rounded-xl border border-[#EAECF0] p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><span className="mr-2 rounded-full bg-[#F2F4F7] px-2 py-1 text-[11px] text-[#475467]">{item.category}</span>{item.mandatory && <span className="text-xs font-medium text-[#D92D20]">必答</span>}<p className="mt-2 text-sm text-[#101828]">{item.original_text}</p></div><span className="text-xs text-[#667085]">{item.status}</span></div><div className="mt-3 flex gap-2"><input disabled={!canContribute} value={responses[item.id] || ""} onChange={(event) => setResponses({ ...responses, [item.id]: event.target.value })} placeholder="录入响应要点" className="h-9 flex-1 rounded-lg border border-[#D9DCE3] px-3 text-sm disabled:bg-[#F8F9FC]" />{canContribute && <button type="button" onClick={() => void answerRequirement(item)} disabled={pending === `requirement-${item.id}`} className="h-9 rounded-lg border border-[#D9DCE3] px-3 text-xs font-medium">保存响应</button>}</div></article>)}{requirements.length === 0 && <p className="py-8 text-center text-sm text-[#98A2B3]">尚未录入或抽取需求</p>}</div>
        </section>

        <section className="mt-5 rounded-2xl border border-[#E3E4EA] bg-white p-6">
          <div className="flex items-center justify-between"><div><h2 className="font-semibold text-[#101828]">投标策略纸</h2><p className="mt-1 text-xs text-[#667085]">每行一个策略要点；确认版本不可覆盖。</p></div><span className="text-xs text-[#667085]">v{strategy.version_no} · {strategy.status}</span></div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">{strategyFields.map(([key, label]) => <label key={key} className="grid gap-1.5 text-xs font-medium text-[#475467]">{label}<textarea disabled={!canContribute || strategy.status === "confirmed"} value={strategyDraft[key] || ""} onChange={(event) => setStrategyDraft({ ...strategyDraft, [key]: event.target.value })} rows={4} placeholder="每行填写一个要点" className="rounded-lg border border-[#D9DCE3] p-3 text-sm font-normal text-[#101828] disabled:bg-[#F8F9FC]" /></label>)}</div>
          <div className="mt-4 flex justify-end gap-2">{canContribute && strategy.status !== "confirmed" && <button type="button" onClick={() => void saveStrategy()} disabled={pending === "strategy-save"} className="inline-flex h-9 items-center gap-1 rounded-lg border border-[#D9DCE3] px-3 text-sm"><Save className="h-4 w-4" /> 保存草稿</button>}{canConfirmStrategy && strategy.status !== "confirmed" && <button type="button" onClick={() => void execute("strategy-confirm", () => EnterpriseApi.confirmBidStrategy(project.id))} disabled={pending === "strategy-confirm" || dashboard.strategy_blockers.length > 0} className="h-9 rounded-lg bg-[#17171B] px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40">确认策略纸</button>}</div>
        </section>

        <section id="collaboration" className="mt-5 scroll-mt-40 rounded-2xl border border-[#E3E4EA] bg-white p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="font-semibold text-[#101828]">专业模块协同</h2><p className="mt-1 text-xs text-[#667085]">医学、运营、数统共享同一策略和资料快照。</p></div>{collaboration.modules.length === 0 && canConfirmStrategy && <button type="button" disabled={strategy.status !== "confirmed" || pending === "modules-init"} onClick={() => void execute("modules-init", () => EnterpriseApi.initializeBidModules(project.id))} className="h-9 rounded-lg bg-[#635BFF] px-3 text-sm font-medium text-white disabled:opacity-40">初始化三模块</button>}</div>
          <div className="mt-4 grid gap-4 lg:grid-cols-3">{collaboration.modules.map((module) => <article key={module.id} className="rounded-xl border border-[#EAECF0] p-4"><div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-[#101828]">{{ medical: "医学方案", operations: "运营方案", statistics: "数统方案" }[module.module_type]}</h3><span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-[11px]">{module.status}</span></div><textarea disabled={!canContribute || ["in_review", "approved"].includes(module.status)} value={moduleDrafts[module.id] || ""} onChange={(event) => setModuleDrafts({ ...moduleDrafts, [module.id]: event.target.value })} rows={6} placeholder="专业方案摘要、关键表格和页面建议" className="mt-3 w-full rounded-lg border border-[#D9DCE3] p-3 text-sm disabled:bg-[#F8F9FC]" /><div className="mt-3 flex flex-wrap justify-end gap-2">{canContribute && ["draft", "rejected"].includes(module.status) && <><button type="button" onClick={() => void saveModule(module.id, module.row_version)} className="h-8 rounded-lg border border-[#D9DCE3] px-2.5 text-xs">保存</button><button type="button" disabled={!moduleDrafts[module.id]?.trim()} onClick={() => void execute(`submit-${module.id}`, () => EnterpriseApi.submitBidModule(project.id, module.id))} className="h-8 rounded-lg bg-[#087BCB] px-2.5 text-xs text-white disabled:opacity-40">提交审核</button></>}{canReview && module.status === "in_review" && <><button type="button" onClick={() => void execute(`reject-${module.id}`, () => EnterpriseApi.reviewBidModule(project.id, module.id, "reject", "请修改后重新提交"))} className="h-8 rounded-lg border border-[#FDA29B] px-2.5 text-xs text-[#B42318]">退回</button><button type="button" onClick={() => void execute(`approve-${module.id}`, () => EnterpriseApi.reviewBidModule(project.id, module.id, "approve", "专业审核通过"))} className="h-8 rounded-lg bg-[#027A48] px-2.5 text-xs text-white">批准</button></>}</div></article>)}</div>
        </section>

        <div id="gates" className="mt-5 scroll-mt-40 grid gap-5 lg:grid-cols-[1.2fr_1fr]">
          <section className="rounded-2xl border border-[#E3E4EA] bg-white p-6"><h2 className="font-semibold text-[#101828]">服务承诺审批</h2>{canContribute && <form onSubmit={createCommitment} className="mt-4 grid gap-2"><input value={commitmentDraft.content} onChange={(event) => setCommitmentDraft({ ...commitmentDraft, content: event.target.value })} placeholder="承诺内容" className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm" /><div className="grid gap-2 sm:grid-cols-[140px_1fr_auto]"><select value={commitmentDraft.commitment_type} onChange={(event) => setCommitmentDraft({ ...commitmentDraft, commitment_type: event.target.value })} className="h-9 rounded-lg border border-[#D9DCE3] bg-white px-2 text-sm"><option value="timeline">周期</option><option value="quality">质量</option><option value="resource">资源</option></select><input value={commitmentDraft.evidence_ref} onChange={(event) => setCommitmentDraft({ ...commitmentDraft, evidence_ref: event.target.value })} placeholder="历史依据/证据引用" className="h-9 rounded-lg border border-[#D9DCE3] px-3 text-sm" /><button disabled={!commitmentDraft.content.trim()} className="h-9 rounded-lg bg-[#17171B] px-3 text-xs text-white disabled:opacity-40">添加候选</button></div></form>}<div className="mt-4 grid gap-2">{collaboration.commitments.map((item) => <article key={item.id} className="rounded-lg bg-[#F8F9FC] p-3"><div className="flex items-start justify-between gap-3"><p className="text-sm text-[#101828]">{item.content}</p><span className="text-xs text-[#667085]">{item.status}</span></div><p className="mt-1 text-xs text-[#98A2B3]">依据：{item.evidence_ref || "未填写"}</p><div className="mt-2 flex justify-end gap-2">{canContribute && item.status === "candidate" && <button onClick={() => void execute(`commitment-${item.id}`, () => EnterpriseApi.actOnBidCommitment(project.id, item.id, "submit"))} className="text-xs text-[#635BFF]">提交审批</button>}{canConfirmStrategy && item.status === "pending" && <button onClick={() => void execute(`commitment-${item.id}`, () => EnterpriseApi.actOnBidCommitment(project.id, item.id, "approve"))} className="text-xs text-[#027A48]">批准</button>}</div></article>)}</div></section>
          <section className="rounded-2xl border border-[#E3E4EA] bg-white p-6">
            <h2 className="font-semibold text-[#101828]">Gate 1 / Gate 2 / Gate 3</h2>
            <p className="mt-1 text-xs text-[#667085]">登记阻断与风险、记录处置依据，通过动作由实际检查结果驱动。</p>
            <div className="mt-4 grid gap-3">
              {collaboration.gates.map((gate) => {
                const draft = issueDrafts[gate.id] || { title: "", description: "", severity: "blocking" as const };
                return (
                  <article key={gate.id} className="rounded-xl border border-[#EAECF0] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-[#101828]">{{ gate_1: "Gate 1 专业正确性", gate_2: "Gate 2 客户决策逻辑", gate_3: "Gate 3 演练与冻结" }[gate.gate_type]}</p>
                        <p className="mt-1 text-xs text-[#667085]">{gate.status} · {gate.issues.filter((item) => item.status === "open").length} 个未关闭问题</p>
                      </div>
                      {canReview && gate.status !== "passed" && (
                        <div className="flex gap-2">
                          <button type="button" onClick={() => void execute(`${gate.id}-open`, () => EnterpriseApi.actOnBidGate(project.id, gate.gate_type, "open"))} className="h-8 rounded-lg border border-[#D9DCE3] px-2 text-xs">执行检查</button>
                          <button type="button" disabled={gate.issues.some((item) => item.status === "open" && item.severity === "blocking")} onClick={() => void execute(`${gate.id}-pass`, () => EnterpriseApi.actOnBidGate(project.id, gate.gate_type, "pass"))} className="h-8 rounded-lg bg-[#027A48] px-2 text-xs text-white disabled:opacity-40">确认通过</button>
                        </div>
                      )}
                    </div>
                    {gate.issues.length > 0 && (
                      <div className="mt-3 grid gap-2">
                        {gate.issues.map((issue) => (
                          <div key={issue.id} className={`rounded-lg p-3 ${issue.status === "resolved" ? "bg-[#F8F9FC]" : issue.severity === "blocking" ? "bg-[#FEF3F2]" : "bg-[#FFFAEB]"}`}>
                            <div className="flex items-start justify-between gap-2"><p className="text-xs font-medium text-[#344054]">{issue.title}</p><span className="text-[10px] text-[#667085]">{issue.severity === "blocking" ? "阻断" : "提示"} · {issue.status === "resolved" ? "已关闭" : "待处置"}</span></div>
                            {issue.description && <p className="mt-1 text-xs text-[#667085]">{issue.description}</p>}
                            {issue.resolution && <p className="mt-2 text-xs text-[#027A48]">处置记录：{issue.resolution}</p>}
                            {canReview && issue.status === "open" && (
                              <div className="mt-2 flex gap-2">
                                <input value={resolutionDrafts[issue.id] || ""} onChange={(event) => setResolutionDrafts({ ...resolutionDrafts, [issue.id]: event.target.value })} placeholder="填写处置依据后关闭" className="h-8 min-w-0 flex-1 rounded-lg border border-[#D9DCE3] bg-white px-2 text-xs" />
                                <button type="button" disabled={!resolutionDrafts[issue.id]?.trim()} onClick={() => void resolveGateIssue(issue.id)} className="h-8 rounded-lg border border-[#039855] bg-white px-2 text-xs text-[#027A48] disabled:opacity-40">关闭问题</button>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    {canReview && gate.status !== "passed" && (
                      <div className="mt-3 grid gap-2 border-t border-[#EAECF0] pt-3">
                        <div className="grid gap-2 sm:grid-cols-[110px_1fr]">
                          <select value={draft.severity} onChange={(event) => setIssueDrafts({ ...issueDrafts, [gate.id]: { ...draft, severity: event.target.value as "blocking" | "warning" } })} className="h-8 rounded-lg border border-[#D9DCE3] bg-white px-2 text-xs"><option value="blocking">阻断问题</option><option value="warning">风险提示</option></select>
                          <input value={draft.title} onChange={(event) => setIssueDrafts({ ...issueDrafts, [gate.id]: { ...draft, title: event.target.value } })} placeholder="问题标题" className="h-8 rounded-lg border border-[#D9DCE3] px-2 text-xs" />
                        </div>
                        <div className="flex gap-2">
                          <input value={draft.description} onChange={(event) => setIssueDrafts({ ...issueDrafts, [gate.id]: { ...draft, description: event.target.value } })} placeholder="问题描述、影响和建议动作" className="h-8 min-w-0 flex-1 rounded-lg border border-[#D9DCE3] px-2 text-xs" />
                          <button type="button" disabled={!draft.title.trim()} onClick={() => void createGateIssue(gate)} className="h-8 rounded-lg bg-[#17171B] px-3 text-xs text-white disabled:opacity-40">登记问题</button>
                        </div>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          </section>
        </div>

        <section className="mt-5 rounded-2xl border border-[#E3E4EA] bg-white p-6">
          <div className="flex items-center gap-2"><Activity className="h-4 w-4 text-[#635BFF]" /><h2 className="font-semibold text-[#101828]">项目动态</h2></div>
          <p className="mt-1 text-xs text-[#667085]">展示成员、专业模块、承诺、Gate 和版本操作形成的审计轨迹。</p>
          <div className="mt-4 grid gap-1">
            {activity.map((event) => (
              <div key={event.id} className="grid gap-1 border-l-2 border-[#E4E1FF] py-2 pl-4 sm:grid-cols-[1fr_auto]">
                <div><p className="text-sm text-[#344054]">{event.action.replaceAll("_", " · ").replace("bid.", "")}</p><p className="mt-0.5 text-[11px] text-[#98A2B3]">{event.resource_type}</p></div>
                <time className="text-xs text-[#667085]">{new Date(event.created_at).toLocaleString("zh-CN")}</time>
              </div>
            ))}
            {activity.length === 0 && <p className="py-5 text-center text-sm text-[#98A2B3]">当前项目暂无可展示的动态记录</p>}
          </div>
        </section>

        <section id="assembly" className="mt-5 scroll-mt-40 rounded-2xl border border-[#E3E4EA] bg-white p-6">
          <span id="delivery" className="block scroll-mt-40" />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="font-semibold text-[#101828]">专业组装与冻结版本</h2><p className="mt-1 text-xs text-[#667085]">仅使用已批准模块、承诺和已发布模板生成可重现摘要。</p></div>{canConfirmStrategy && <div className="flex gap-2"><select value={templatePublicationId} onChange={(event) => setTemplatePublicationId(event.target.value)} className="h-9 rounded-lg border border-[#D9DCE3] bg-white px-2 text-xs">{templates.map((item) => <option key={item.id} value={item.id}>{item.display_name} · v{item.version}</option>)}</select><button type="button" disabled={!templatePublicationId || collaboration.gates.find((gate) => gate.gate_type === "gate_2")?.status !== "passed"} onClick={() => void execute("assemble", () => EnterpriseApi.assembleBidRelease(project.id, templatePublicationId))} className="h-9 rounded-lg bg-[#635BFF] px-3 text-xs font-medium text-white disabled:opacity-40">生成管理层摘要</button></div>}</div>
          <div className="mt-4 grid gap-3">{releases.map((release) => <article key={release.id} className="rounded-xl border border-[#EAECF0] p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><div className="flex items-center gap-2"><span className="text-sm font-semibold text-[#101828]">管理层摘要 v{release.version_no}</span><span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-[11px]">{release.status}</span></div><p className="mt-1 font-mono text-[11px] text-[#98A2B3]">manifest {release.manifest_hash.slice(0, 16)}…</p></div><div className="flex flex-wrap gap-2">{release.manifest.presentation_id && <Link href={`/presentation?id=${encodeURIComponent(release.manifest.presentation_id)}&type=standard`} className="inline-flex h-8 items-center rounded-lg border border-[#D9DCE3] px-2.5 text-xs">打开预览</Link>}{canConfirmStrategy && release.status === "draft" && <><button type="button" onClick={() => void execute(`quality-${release.id}`, () => EnterpriseApi.runPresentationQuality(project.workspace_id, release.presentation_entry_id))} className="h-8 rounded-lg border border-[#087BCB] px-2.5 text-xs text-[#087BCB]">统一质量检查</button><button type="button" disabled={collaboration.gates.find((gate) => gate.gate_type === "gate_3")?.status !== "passed"} onClick={() => void execute(`freeze-${release.id}`, () => EnterpriseApi.freezeBidRelease(project.id, release.id))} className="h-8 rounded-lg bg-[#17171B] px-2.5 text-xs text-white disabled:opacity-40">冻结版本</button></>}{canConfirmStrategy && ["frozen", "archived"].includes(release.status) && <><button type="button" disabled={pending === `export-pptx-${release.id}`} onClick={() => void execute(`export-pptx-${release.id}`, () => EnterpriseApi.createBidDelivery(project.id, release.id, "pptx"))} className="h-8 rounded-lg bg-[#635BFF] px-2.5 text-xs text-white disabled:opacity-40">导出 PPTX</button><button type="button" disabled={pending === `export-pdf-${release.id}`} onClick={() => void execute(`export-pdf-${release.id}`, () => EnterpriseApi.createBidDelivery(project.id, release.id, "pdf"))} className="h-8 rounded-lg border border-[#635BFF] px-2.5 text-xs text-[#4238CA] disabled:opacity-40">导出 PDF</button></>}{canConfirmStrategy && release.status === "frozen" && (deliveries[release.id]?.length || 0) > 0 && <button type="button" onClick={() => void execute(`archive-${release.id}`, () => EnterpriseApi.archiveBidRelease(project.id, release.id))} className="h-8 rounded-lg border border-[#D9DCE3] px-2.5 text-xs">归档</button>}</div></div>{(deliveries[release.id]?.length || 0) > 0 && <div className="mt-3 grid gap-2 border-t border-[#EAECF0] pt-3">{deliveries[release.id].map((artifact) => <div key={artifact.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-[#F8F9FC] px-3 py-2"><div><p className="text-xs font-medium uppercase text-[#344054]">{artifact.format} · {(artifact.size_bytes / 1024).toFixed(1)} KB · {artifact.status === "revoked" ? "已撤销" : "可交付"}</p><p className="mt-0.5 font-mono text-[10px] text-[#98A2B3]">SHA-256 {artifact.sha256.slice(0, 16)}… · 水印：{artifact.watermark_text}</p></div><div className="flex gap-2">{artifact.status === "ready" && <button type="button" disabled={pending === `download-${artifact.id}`} onClick={() => void downloadDelivery(artifact.id)} className="inline-flex h-8 items-center gap-1 rounded-lg border border-[#D9DCE3] bg-white px-2.5 text-xs disabled:opacity-40"><Download className="h-3.5 w-3.5" />授权下载</button>}{canConfirmStrategy && artifact.status === "ready" && <button type="button" disabled={pending === `revoke-delivery-${artifact.id}`} onClick={() => void execute(`revoke-delivery-${artifact.id}`, () => EnterpriseApi.revokeBidDelivery(project.id, artifact.id))} className="inline-flex h-8 items-center gap-1 rounded-lg border border-[#FDA29B] bg-white px-2.5 text-xs text-[#B42318] disabled:opacity-40"><Ban className="h-3.5 w-3.5" />撤销交付</button>}</div></div>)}</div>}</article>)}{releases.length === 0 && <p className="py-8 text-center text-sm text-[#98A2B3]">Gate 2 通过后可生成第一版摘要。</p>}</div>
        </section>
      </div>
    </main>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <article className="rounded-xl border border-[#E3E4EA] bg-white p-4"><p className="text-xs text-[#667085]">{label}</p><p className="mt-2 text-xl font-semibold text-[#101828]">{value}</p><p className="mt-1 text-xs text-[#98A2B3]">{detail}</p></article>;
}

export default BidProjectDashboardPage;
