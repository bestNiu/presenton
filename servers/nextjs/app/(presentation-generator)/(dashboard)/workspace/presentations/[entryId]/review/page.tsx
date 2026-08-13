"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { AlertTriangle, ArrowLeft, CheckCircle2, GitCompareArrows, MessageSquarePlus } from "lucide-react";

import {
  EnterpriseApi,
  type PresentationCommentThreadResponse,
  type PresentationGovernanceResponse,
  type PresentationFreezePreflightResponse,
  type PresentationSnapshotDiffResponse,
  type PresentationSnapshotEvidenceResponse,
  type PresentationDeliveryArtifactResponse,
  type PresentationDeliveryEvidenceResponse,
  type AuditEventResponse,
  type PresentationDeliveryEvidenceVerifyResponse,
  type WorkspaceMemberResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";

const diffFieldLabel: Record<string, string> = {
  ui: "画布",
  content: "内容",
  speaker_note: "演讲者备注",
  index: "页面顺序",
};

export default function PresentationReviewPage() {
  const params = useParams<{ entryId: string }>();
  const searchParams = useSearchParams();
  const entryId = params.entryId;
  const workspaceId = searchParams.get("workspace_id") || "";
  const [governance, setGovernance] = useState<PresentationGovernanceResponse | null>(null);
  const [preflight, setPreflight] = useState<PresentationFreezePreflightResponse | null>(null);
  const [canFreeze, setCanFreeze] = useState(false);
  const [threads, setThreads] = useState<PresentationCommentThreadResponse[]>([]);
  const [diff, setDiff] = useState<PresentationSnapshotDiffResponse | null>(null);
  const [evidence, setEvidence] = useState<PresentationSnapshotEvidenceResponse | null>(null);
  const [deliveries, setDeliveries] = useState<PresentationDeliveryArtifactResponse[]>([]);
  const [deliveryEvidence, setDeliveryEvidence] = useState<PresentationDeliveryEvidenceResponse | null>(null);
  const [deliveryActivity, setDeliveryActivity] = useState<AuditEventResponse[]>([]);
  const [packageVerification, setPackageVerification] = useState<PresentationDeliveryEvidenceVerifyResponse | null>(null);
  const [members, setMembers] = useState<WorkspaceMemberResponse[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [slideIndex, setSlideIndex] = useState("");
  const [blocking, setBlocking] = useState(true);
  const [assignee, setAssignee] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({});
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!workspaceId) return;
    setError(null);
    try {
      const [governanceResult, commentResult, memberResult, preflightResult, workspaces, deliveryResult] = await Promise.all([
        EnterpriseApi.getPresentationGovernance(workspaceId, entryId),
        EnterpriseApi.getPresentationComments(workspaceId, entryId),
        EnterpriseApi.getWorkspaceMembers(workspaceId),
        EnterpriseApi.getPresentationFreezePreflight(workspaceId, entryId),
        EnterpriseApi.getWorkspaces(),
        EnterpriseApi.getPresentationDeliveries(workspaceId, entryId),
      ]);
      setGovernance(governanceResult);
      setThreads(commentResult);
      setMembers(memberResult);
      setPreflight(preflightResult);
      setDeliveries(deliveryResult);
      const workspace = workspaces.find((item) => item.id === workspaceId);
      setCanFreeze(Boolean(workspace && ["owner", "admin"].includes(workspace.current_user_role)));
      if (governanceResult.snapshots.length >= 2) {
        setDiff(await EnterpriseApi.comparePresentationSnapshots(workspaceId, entryId, governanceResult.snapshots[1].id, governanceResult.snapshots[0].id));
      } else {
        setDiff(null);
      }
      if (governanceResult.snapshots[0]) {
        setEvidence(await EnterpriseApi.getPresentationSnapshotEvidence(workspaceId, entryId, governanceResult.snapshots[0].id));
      } else {
        setEvidence(null);
      }
      if (deliveryResult[0]) {
        setDeliveryEvidence(await EnterpriseApi.getPresentationDeliveryEvidence(workspaceId, entryId, deliveryResult[0].id));
      } else {
        setDeliveryEvidence(null);
        setDeliveryActivity([]);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "评审批注加载失败");
    }
  }, [entryId, workspaceId]);

  useEffect(() => { void load(); }, [load]);

  const openCount = useMemo(() => threads.filter((thread) => thread.status === "open").length, [threads]);
  const blockingCount = useMemo(() => threads.filter((thread) => thread.status === "open" && thread.is_blocking).length, [threads]);

  const createThread = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim() || !body.trim()) return;
    setPending(true);
    try {
      await EnterpriseApi.createPresentationComment(workspaceId, entryId, {
        title: title.trim(),
        body: body.trim(),
        is_blocking: blocking,
        ...(slideIndex ? { slide_index: Number(slideIndex) - 1 } : {}),
        ...(assignee ? { assigned_to: assignee } : {}),
        ...(dueAt ? { due_at: new Date(dueAt).toISOString() } : {}),
      });
      setTitle(""); setBody(""); setSlideIndex(""); setAssignee(""); setDueAt("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "整改项创建失败");
    } finally { setPending(false); }
  };

  const transition = async (thread: PresentationCommentThreadResponse) => {
    setPending(true);
    try {
      await EnterpriseApi.transitionPresentationComment(workspaceId, entryId, thread.id, thread.status === "open" ? "resolve" : "reopen");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "整改状态更新失败");
    } finally { setPending(false); }
  };

  const reply = async (threadId: string) => {
    const replyBody = replyDrafts[threadId]?.trim();
    if (!replyBody) return;
    setPending(true);
    try {
      await EnterpriseApi.replyPresentationComment(workspaceId, entryId, threadId, replyBody);
      setReplyDrafts((current) => ({ ...current, [threadId]: "" }));
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "回复发送失败");
    } finally { setPending(false); }
  };

  const freeze = async () => {
    setPending(true);
    try {
      await EnterpriseApi.freezePresentation(workspaceId, entryId);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "冻结失败，请按预检清单整改");
    } finally { setPending(false); }
  };

  const verifyDelivery = async (artifactId: string) => {
    setPending(true);
    try {
      setDeliveryEvidence(await EnterpriseApi.getPresentationDeliveryEvidence(workspaceId, entryId, artifactId));
      if (canFreeze) setDeliveryActivity(await EnterpriseApi.getPresentationDeliveryActivity(workspaceId, entryId, artifactId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "交付凭证校验失败");
    } finally { setPending(false); }
  };

  const verifyEvidenceFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setPending(true);
    try {
      const evidencePackage = JSON.parse(await file.text()) as Record<string, unknown>;
      const artifactPayload = evidencePackage.artifact as Record<string, unknown> | undefined;
      const artifactId = typeof artifactPayload?.id === "string" ? artifactPayload.id : "";
      if (!deliveries.some((item) => item.id === artifactId)) throw new Error("证据包不属于当前文稿交付件");
      setPackageVerification(await EnterpriseApi.verifyPresentationDeliveryEvidencePackage(workspaceId, entryId, artifactId, evidencePackage));
      setError(null);
    } catch (cause) {
      setPackageVerification(null);
      setError(cause instanceof Error ? cause.message : "证据包解析或验证失败");
    } finally { setPending(false); }
  };

  if (!workspaceId) return <main className="p-8 text-sm text-[#B42318]">缺少 workspace_id，无法打开评审中心。</main>;

  return (
    <main className="min-h-screen bg-[#F7F7FA] px-6 py-8 text-[#101828]">
      <div className="mx-auto max-w-6xl">
        <Link href="/workspace" className="inline-flex items-center gap-2 text-sm text-[#475467]"><ArrowLeft className="h-4 w-4" />返回通用 PPT 工作台</Link>
        <div className="mt-5 flex flex-wrap items-end justify-between gap-4">
          <div><p className="text-xs font-medium text-[#635BFF]">企业演示评审中心</p><h1 className="mt-1 text-2xl font-semibold">{governance?.entry.title || "演示文稿"}</h1><p className="mt-2 text-sm text-[#667085]">页级评论、整改责任与冻结版本差异统一留痕，竞标及通用文稿均适用。</p></div>
          <div className="flex gap-2 text-xs"><Link href={governance ? `/presentation?id=${encodeURIComponent(governance.entry.presentation_id)}&type=standard&workspace_id=${encodeURIComponent(workspaceId)}&entry_id=${encodeURIComponent(entryId)}` : "#"} className="rounded-full bg-[#17171B] px-3 py-2 text-white">进入画布整改</Link><span className="rounded-full bg-white px-3 py-2">待处理 {openCount}</span><span className="rounded-full bg-[#FEF2F2] px-3 py-2 text-[#B42318]">阻断 {blockingCount}</span></div>
        </div>
        {error && <div className="mt-4 rounded-xl border border-[#FDA29B] bg-[#FEF2F2] p-3 text-sm text-[#B42318]">{error}</div>}

        <div className="mt-6 grid gap-5 lg:grid-cols-[1fr_360px]">
          <section className="space-y-3">
            {threads.length === 0 && <div className="rounded-2xl border border-dashed border-[#D9DCE3] bg-white p-10 text-center text-sm text-[#667085]">暂无评论或整改待办</div>}
            {threads.map((thread) => <article key={thread.id} className="rounded-2xl border border-[#E3E4EA] bg-white p-5">
              <div className="flex items-start justify-between gap-3"><div><div className="flex items-center gap-2">{thread.is_blocking ? <AlertTriangle className="h-4 w-4 text-[#D92D20]" /> : <CheckCircle2 className="h-4 w-4 text-[#667085]" />}<h2 className="font-semibold">{thread.title}</h2></div><p className="mt-2 text-sm leading-6 text-[#475467]">{thread.body}</p></div><span className={`rounded-full px-2.5 py-1 text-xs ${thread.status === "open" ? "bg-[#FFF4E5] text-[#B54708]" : "bg-[#ECFDF3] text-[#027A48]"}`}>{thread.status === "open" ? "待整改" : "已解决"}</span></div>
              {thread.replies.length > 0 && <div className="mt-4 space-y-2 rounded-xl bg-[#F8F9FC] p-3">{thread.replies.map((item) => <p key={item.id} className="text-xs leading-5 text-[#475467]">{item.body}<span className="ml-2 text-[#98A2B3]">{new Date(item.created_at).toLocaleString()}</span></p>)}</div>}
              <div className="mt-3 flex gap-2"><input value={replyDrafts[thread.id] || ""} onChange={(event) => setReplyDrafts((current) => ({ ...current, [thread.id]: event.target.value }))} placeholder="回复或补充整改说明" className="h-9 flex-1 rounded-lg border border-[#D9DCE3] px-3 text-xs" /><button type="button" disabled={pending || !replyDrafts[thread.id]?.trim()} onClick={() => void reply(thread.id)} className="rounded-lg bg-[#F2F1FF] px-3 text-xs text-[#4238CA] disabled:opacity-40">回复</button></div>
              <div className="mt-4 flex items-center justify-between border-t border-[#F0F1F3] pt-3 text-xs text-[#667085]"><span>{thread.slide_index === null ? "全稿" : `第 ${thread.slide_index + 1} 页`} · {thread.assigned_to ? `责任人：${members.find((member) => member.user_id === thread.assigned_to)?.username || "成员"}` : "未指派"}{thread.due_at ? ` · 截止 ${new Date(thread.due_at).toLocaleDateString()}` : ""}</span><button disabled={pending} onClick={() => void transition(thread)} className="rounded-lg border border-[#D9DCE3] px-3 py-1.5 text-[#344054] disabled:opacity-40">{thread.status === "open" ? "标记解决" : "重新打开"}</button></div>
            </article>)}
          </section>

          <aside className="space-y-5">
            <div className="rounded-2xl border border-[#E3E4EA] bg-white p-5"><div className="flex items-center justify-between gap-2"><div className="font-semibold">冻结前预检</div><span className={`rounded-full px-2.5 py-1 text-xs ${preflight?.can_freeze ? "bg-[#ECFDF3] text-[#027A48]" : "bg-[#FFF4E5] text-[#B54708]"}`}>{preflight?.can_freeze ? "可冻结" : "待处理"}</span></div><div className="mt-4 space-y-2">{preflight?.checks.map((check) => <div key={check.code} className="flex items-start gap-2 rounded-lg bg-[#F8F9FC] p-2.5">{check.passed ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#039855]" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#D92D20]" />}<div><p className="text-xs font-medium text-[#344054]">{check.label}</p><p className="mt-0.5 text-xs text-[#667085]">{check.message}</p></div></div>)}</div>{canFreeze && <button type="button" onClick={() => void freeze()} disabled={pending || !preflight?.can_freeze} className="mt-4 h-10 w-full rounded-lg bg-[#17171B] text-sm font-medium text-white disabled:opacity-40">冻结当前版本</button>}</div>
            <form onSubmit={createThread} className="rounded-2xl border border-[#E3E4EA] bg-white p-5"><div className="flex items-center gap-2 font-semibold"><MessageSquarePlus className="h-4 w-4 text-[#635BFF]" />新增整改项</div><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="问题标题" className="mt-4 h-10 w-full rounded-lg border border-[#D9DCE3] px-3 text-sm" /><textarea value={body} onChange={(event) => setBody(event.target.value)} placeholder="说明问题与验收要求" rows={4} className="mt-3 w-full rounded-lg border border-[#D9DCE3] p-3 text-sm" /><input type="number" min="1" value={slideIndex} onChange={(event) => setSlideIndex(event.target.value)} placeholder="页码（可选）" className="mt-3 h-10 w-full rounded-lg border border-[#D9DCE3] px-3 text-sm" /><select value={assignee} onChange={(event) => setAssignee(event.target.value)} className="mt-3 h-10 w-full rounded-lg border border-[#D9DCE3] bg-white px-3 text-sm"><option value="">未指派责任人</option>{members.map((member) => <option key={member.user_id} value={member.user_id}>{member.username} · {member.role}</option>)}</select><input type="date" value={dueAt} onChange={(event) => setDueAt(event.target.value)} className="mt-3 h-10 w-full rounded-lg border border-[#D9DCE3] px-3 text-sm" /><label className="mt-3 flex items-center gap-2 text-sm text-[#475467]"><input type="checkbox" checked={blocking} onChange={(event) => setBlocking(event.target.checked)} />审批前必须解决</label><button disabled={pending || !title.trim() || !body.trim()} className="mt-4 h-10 w-full rounded-lg bg-[#635BFF] text-sm font-medium text-white disabled:opacity-40">创建整改项</button></form>
            <div className="rounded-2xl border border-[#E3E4EA] bg-white p-5"><div className="flex items-center gap-2 font-semibold"><GitCompareArrows className="h-4 w-4 text-[#635BFF]" />版本差异</div>{diff ? <div className="mt-4 text-sm text-[#475467]"><p>V{diff.from_version_no} → V{diff.to_version_no}</p><div className="mt-3 grid grid-cols-2 gap-2 text-xs"><span className="rounded-lg bg-[#ECFDF3] p-2">新增 {diff.added}</span><span className="rounded-lg bg-[#FFF4E5] p-2">修改 {diff.changed}</span><span className="rounded-lg bg-[#FEF2F2] p-2">删除 {diff.removed}</span><span className="rounded-lg bg-[#F2F4F7] p-2">未变 {diff.unchanged}</span></div>{diff.slides.some((slide) => slide.change_type !== "unchanged") && <div className="mt-4 space-y-2 border-t border-[#F0F1F3] pt-3">{diff.slides.filter((slide) => slide.change_type !== "unchanged").map((slide) => <div key={slide.slide_id} className="rounded-lg bg-[#F8F9FC] p-2.5 text-xs"><div className="flex items-center justify-between"><span>{slide.change_type === "added" ? `新增第 ${(slide.after_index ?? 0) + 1} 页` : slide.change_type === "removed" ? `删除原第 ${(slide.before_index ?? 0) + 1} 页` : `修改第 ${(slide.after_index ?? 0) + 1} 页`}</span><span className={slide.change_type === "changed" ? "text-[#B54708]" : slide.change_type === "added" ? "text-[#027A48]" : "text-[#B42318]"}>{slide.change_type}</span></div>{slide.changed_fields.length > 0 && <p className="mt-1 text-[#667085]">变化字段：{slide.changed_fields.map((field) => diffFieldLabel[field] || field).join("、")}</p>}</div>)}</div>}</div> : <p className="mt-3 text-sm text-[#667085]">至少形成两个冻结版本后自动展示逐页差异。</p>}</div>
            {evidence && <div className="rounded-2xl border border-[#E3E4EA] bg-white p-5"><div className="flex items-center justify-between"><div className="font-semibold">V{evidence.version_no} 冻结证据</div><span className={`rounded-full px-2 py-1 text-xs ${evidence.manifest_integrity && evidence.citation_integrity ? "bg-[#ECFDF3] text-[#027A48]" : "bg-[#FEF2F2] text-[#B42318]"}`}>{evidence.manifest_integrity && evidence.citation_integrity ? "完整性通过" : "完整性异常"}</span></div><p className="mt-2 break-all text-[10px] text-[#98A2B3]">{evidence.manifest_hash}</p><div className="mt-3 space-y-2">{evidence.citations.length === 0 ? <p className="rounded-lg bg-[#F8F9FC] p-3 text-xs text-[#667085]">该冻结版本无引用证据。</p> : evidence.citations.map((item) => <div key={item.id} className="rounded-lg bg-[#F8F9FC] p-2.5 text-xs"><p className="font-medium text-[#344054]">{item.source_name || item.source_id} · v{item.source_version || "-"}</p><p className="mt-1 text-[#667085]">{item.locator || "无定位"} · 冻结时 {item.status}</p>{item.excerpt && <p className="mt-1 line-clamp-2 text-[#475467]">{item.excerpt}</p>}</div>)}</div></div>}
            {deliveries.length > 0 && <div className="rounded-2xl border border-[#E3E4EA] bg-white p-5"><div className="font-semibold">受控交付凭证</div><div className="mt-3 space-y-2">{deliveries.map((artifact) => <button type="button" key={artifact.id} onClick={() => void verifyDelivery(artifact.id)} disabled={pending} className="w-full rounded-lg border border-[#EAECF0] p-3 text-left disabled:opacity-40"><div className="flex items-center justify-between gap-2"><span className="text-xs font-medium uppercase">{artifact.format} · {(artifact.size_bytes / 1024).toFixed(1)} KB</span><span className={`rounded-full px-2 py-1 text-[10px] ${artifact.status === "ready" ? "bg-[#ECFDF3] text-[#027A48]" : "bg-[#FEF2F2] text-[#B42318]"}`}>{artifact.status === "ready" ? "可交付" : "已撤销"}</span></div><p className="mt-1 font-mono text-[10px] text-[#98A2B3]">{artifact.sha256}</p></button>)}</div>{deliveryEvidence && <div className="mt-3 rounded-lg bg-[#F8F9FC] p-3 text-xs"><p className="font-medium text-[#344054]">凭证 {deliveryEvidence.credential_hash.slice(0, 20)}…</p><div className="mt-2 grid grid-cols-3 gap-1 text-center text-[10px]"><span className={deliveryEvidence.file_integrity ? "text-[#027A48]" : "text-[#B42318]"}>文件{deliveryEvidence.file_integrity ? "通过" : "异常"}</span><span className={deliveryEvidence.snapshot_integrity ? "text-[#027A48]" : "text-[#B42318]"}>快照{deliveryEvidence.snapshot_integrity ? "通过" : "异常"}</span><span className={deliveryEvidence.citation_integrity ? "text-[#027A48]" : "text-[#B42318]"}>引用{deliveryEvidence.citation_integrity ? "通过" : "异常"}</span></div><p className="mt-2 text-[#667085]">关联 V{deliveryEvidence.snapshot_version} · {deliveryEvidence.citation_count} 条引用</p>{canFreeze && <button type="button" onClick={() => void EnterpriseApi.downloadPresentationDeliveryEvidencePackage(workspaceId, entryId, deliveryEvidence.artifact.id)} className="mt-3 w-full rounded-lg border border-[#D9DCE3] bg-white py-2 text-xs text-[#344054]">下载 JSON 证据包</button>}</div>}<label className="mt-3 block cursor-pointer rounded-lg border border-dashed border-[#B9B2FF] p-2 text-center text-xs text-[#4238CA]">上传 JSON 包验证真实性<input type="file" accept="application/json,.json" onChange={(event) => void verifyEvidenceFile(event)} className="hidden" /></label>{packageVerification && <p className={`mt-2 rounded-lg p-2 text-center text-xs ${packageVerification.valid ? "bg-[#ECFDF3] text-[#027A48]" : "bg-[#FEF2F2] text-[#B42318]"}`}>{packageVerification.valid ? "平台签发、包内容及当前交付件均验证通过" : "验证未通过，请检查包完整性、签发记录或当前交付件状态"}</p>}{deliveryActivity.length > 0 && <div className="mt-3 space-y-1 border-t border-[#EAECF0] pt-3">{deliveryActivity.slice(0, 8).map((event) => <p key={event.id} className="text-[10px] text-[#667085]">{new Date(event.created_at).toLocaleString()} · {event.action}</p>)}</div>}</div>}
          </aside>
        </div>
      </div>
    </main>
  );
}
