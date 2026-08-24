"use client";

import Link from "next/link";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Columns3,
  List,
  Loader2,
  RotateCcw,
  Search,
  UserRound,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  EnterpriseApi,
  type PresentationReviewInboxResponse,
  type WorkspaceMemberResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";
import { useEnterpriseWorkspace } from "../components/EnterpriseWorkspaceShell";

type ReviewTask = PresentationReviewInboxResponse["tasks"][number];
type ViewMode = "list" | "board";
type ScopeFilter = "all" | "mine";
type StatusFilter = "open" | "resolved" | "all";
type ConfirmAction = "resolve" | "reopen";

const sceneLabels: Record<string, string> = {
  general: "通用文稿",
  bid: "竞标项目",
  training: "培训课件",
  report: "经营汇报",
};

const statusLabels: Record<string, string> = {
  draft: "草稿",
  in_review: "评审中",
  approved: "已批准",
  frozen: "已冻结",
  archived: "已归档",
};

function taskGroup(task: ReviewTask) {
  if (task.status === "resolved") return "resolved";
  if (task.is_overdue) return "overdue";
  if (task.is_blocking) return "blocking";
  return "open";
}

function dueLabel(task: ReviewTask) {
  if (!task.due_at) return "未设置截止时间";
  const date = new Date(task.due_at);
  return `${task.is_overdue ? "逾期于" : "截止"} ${date.toLocaleDateString("zh-CN")}`;
}

function TaskCard({
  task,
  workspaceId,
  selected,
  selectable,
  onToggle,
}: {
  task: ReviewTask;
  workspaceId: string;
  selected: boolean;
  selectable: boolean;
  onToggle: (taskId: string) => void;
}) {
  return (
    <article className={`rounded-xl border bg-white p-4 transition ${selected ? "border-[#8B7DFF] ring-2 ring-[#E4E1FF]" : "border-[#E4E7EC] hover:border-[#C7C2FF]"}`}>
      <div className="flex items-start gap-3">
        {selectable && (
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggle(task.id)}
            aria-label={`选择任务：${task.title}`}
            className="mt-1 h-4 w-4 rounded border-[#98A2B3] accent-[#635BFF]"
          />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {task.is_blocking && <span className="rounded-full bg-[#FEF2F2] px-2 py-1 text-[10px] font-medium text-[#B42318]">阻断</span>}
            {task.is_overdue && <span className="rounded-full bg-[#FFF4E5] px-2 py-1 text-[10px] font-medium text-[#B54708]">已逾期</span>}
            {task.status === "resolved" && <span className="rounded-full bg-[#ECFDF3] px-2 py-1 text-[10px] font-medium text-[#027A48]">已解决</span>}
            <span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-[10px] text-[#475467]">{sceneLabels[task.scene_type] || task.scene_type}</span>
          </div>
          <h2 className="mt-2 text-sm font-semibold text-[#101828]">{task.title}</h2>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#667085]">{task.body}</p>
          <div className="mt-3 space-y-1 text-xs text-[#667085]">
            <p className="truncate font-medium text-[#344054]">{task.presentation_title}</p>
            <p>{task.slide_index === null ? "全稿任务" : `第 ${task.slide_index + 1} 页`} · {statusLabels[task.presentation_status] || task.presentation_status} · {task.reply_count} 条回复</p>
            <p className="flex items-center gap-1.5"><UserRound className="h-3.5 w-3.5" />{task.assigned_to_username || "未指派责任人"} · {dueLabel(task)}</p>
          </div>
        </div>
      </div>
      <Link
        href={`/workspace/presentations/${encodeURIComponent(task.presentation_entry_id)}/review?workspace_id=${encodeURIComponent(workspaceId)}&thread_id=${encodeURIComponent(task.id)}${task.slide_index === null ? "" : `&slide_index=${task.slide_index}`}`}
        className="mt-4 flex items-center justify-between border-t border-[#F0F1F3] pt-3 text-xs font-medium text-[#5146E5]"
      >
        进入文稿处理 <ChevronRight className="h-4 w-4" />
      </Link>
    </article>
  );
}

export default function WorkspaceReviewTasksPage() {
  const { activeWorkspace, activeWorkspaceId, loading: workspaceLoading } = useEnterpriseWorkspace();
  const [inbox, setInbox] = useState<PresentationReviewInboxResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>("list");
  const [scope, setScope] = useState<ScopeFilter>("all");
  const [status, setStatus] = useState<StatusFilter>("open");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [query, setQuery] = useState("");
  const [scene, setScene] = useState("all");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(null);
  const [members, setMembers] = useState<WorkspaceMemberResponse[]>([]);
  const [bulkAssignee, setBulkAssignee] = useState("");
  const [bulkDueAt, setBulkDueAt] = useState("");

  const canManage = Boolean(activeWorkspace && ["owner", "admin", "reviewer"].includes(activeWorkspace.current_user_role));

  const load = useCallback(async () => {
    if (!activeWorkspaceId) {
      setInbox(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [nextInbox, nextMembers] = await Promise.all([
        EnterpriseApi.getPresentationReviewInbox(activeWorkspaceId, {
          scope,
          taskStatus: status,
          overdueOnly,
        }),
        EnterpriseApi.getWorkspaceMembers(activeWorkspaceId),
      ]);
      setInbox(nextInbox);
      setMembers(nextMembers);
      setSelectedIds(new Set());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "评审任务加载失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }, [activeWorkspaceId, overdueOnly, scope, status]);

  useEffect(() => { void load(); }, [load]);

  const filteredTasks = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return (inbox?.tasks || []).filter((task) => {
      if (scene !== "all" && task.scene_type !== scene) return false;
      if (!normalized) return true;
      return [task.title, task.body, task.presentation_title, task.assigned_to_username || ""]
        .some((value) => value.toLocaleLowerCase().includes(normalized));
    });
  }, [inbox, query, scene]);

  const sceneOptions = useMemo(() => Array.from(new Set((inbox?.tasks || []).map((task) => task.scene_type))).sort(), [inbox]);
  const allVisibleSelected = filteredTasks.length > 0 && filteredTasks.every((task) => selectedIds.has(task.id));
  const selectedVisibleCount = filteredTasks.filter((task) => selectedIds.has(task.id)).length;

  const toggleTask = (taskId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(taskId)) next.delete(taskId); else next.add(taskId);
      return next;
    });
  };

  const toggleVisible = () => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (allVisibleSelected) filteredTasks.forEach((task) => next.delete(task.id));
      else filteredTasks.forEach((task) => next.add(task.id));
      return next;
    });
  };

  const runBulkAction = async () => {
    if (!confirmAction || !activeWorkspaceId) return;
    const selectedTasks = filteredTasks.filter((task) => selectedIds.has(task.id));
    if (!selectedTasks.length) return;
    setPending(true);
    setError(null);
    setNotice(null);
    const results = await Promise.allSettled(selectedTasks.map((task) =>
      EnterpriseApi.transitionPresentationComment(activeWorkspaceId, task.presentation_entry_id, task.id, confirmAction)
    ));
    const succeeded = results.filter((result) => result.status === "fulfilled").length;
    const failed = results.length - succeeded;
    setConfirmAction(null);
    setNotice(`${confirmAction === "resolve" ? "解决" : "重开"}成功 ${succeeded} 项${failed ? `，失败 ${failed} 项` : ""}`);
    if (failed) setError("部分任务处理失败，可能是权限或任务状态已发生变化，请刷新后重试");
    await load();
    setPending(false);
  };

  const applyBulkAssignment = async () => {
    if (!activeWorkspaceId || !selectedVisibleCount || (!bulkAssignee && !bulkDueAt)) return;
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const result = await EnterpriseApi.bulkUpdatePresentationReviewTasks(activeWorkspaceId, {
        thread_ids: filteredTasks.filter((task) => selectedIds.has(task.id)).map((task) => task.id),
        assigned_to: bulkAssignee || undefined,
        due_at: bulkDueAt ? new Date(`${bulkDueAt}T23:59:59`).toISOString() : undefined,
        update_assignee: Boolean(bulkAssignee),
        update_due_at: Boolean(bulkDueAt),
      });
      setNotice(`已更新 ${result.updated_count} 项任务的负责人或截止时间`);
      setBulkAssignee("");
      setBulkDueAt("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "批量指派失败，请稍后重试");
    } finally {
      setPending(false);
    }
  };

  const boardColumns = [
    { key: "overdue", label: "已逾期", tone: "text-[#B42318]", empty: "没有逾期任务" },
    { key: "blocking", label: "阻断整改", tone: "text-[#B54708]", empty: "没有阻断任务" },
    { key: "open", label: "一般待办", tone: "text-[#475467]", empty: "没有一般待办" },
    { key: "resolved", label: "已解决", tone: "text-[#027A48]", empty: "当前筛选下无已解决任务" },
  ] as const;

  return (
    <main className="px-4 py-7 text-[#101828] sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1500px]">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold text-[#635BFF]">跨文稿协作</p>
            <h1 className="mt-1 text-2xl font-semibold">评审任务中心</h1>
            <p className="mt-2 text-sm text-[#667085]">集中跟进通用 PPT 与竞标项目的页级意见、责任人、截止时间和阻断整改。</p>
          </div>
          <div className="flex rounded-lg border border-[#D0D5DD] bg-white p-1" aria-label="任务视图">
            <button type="button" onClick={() => setView("list")} className={`inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-xs ${view === "list" ? "bg-[#F0EEFF] text-[#5146E5]" : "text-[#667085]"}`}><List className="h-3.5 w-3.5" />列表</button>
            <button type="button" onClick={() => setView("board")} className={`inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-xs ${view === "board" ? "bg-[#F0EEFF] text-[#5146E5]" : "text-[#667085]"}`}><Columns3 className="h-3.5 w-3.5" />看板</button>
          </div>
        </div>

        <section className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ["待处理", inbox?.summary.open_count || 0, "text-[#344054]"],
            ["阻断项", inbox?.summary.blocking_count || 0, "text-[#B42318]"],
            ["已逾期", inbox?.summary.overdue_count || 0, "text-[#B54708]"],
            ["分配给我", inbox?.summary.assigned_to_me_count || 0, "text-[#5146E5]"],
          ].map(([label, value, tone]) => <div key={String(label)} className="rounded-xl border border-[#E4E7EC] bg-white p-4"><p className="text-xs text-[#667085]">{label}</p><p className={`mt-2 text-2xl font-semibold ${tone}`}>{value}</p></div>)}
        </section>

        <section className="mt-5 rounded-2xl border border-[#E4E7EC] bg-white p-4">
          <div className="flex flex-wrap items-center gap-3">
            <label className="relative min-w-[240px] flex-1">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-[#98A2B3]" />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索任务、文稿或责任人" className="h-9 w-full rounded-lg border border-[#D0D5DD] pl-9 pr-3 text-sm outline-none focus:border-[#8B7DFF]" />
            </label>
            <select value={scope} onChange={(event) => setScope(event.target.value as ScopeFilter)} className="h-9 rounded-lg border border-[#D0D5DD] bg-white px-3 text-xs"><option value="all">全部责任人</option><option value="mine">只看我的</option></select>
            <select value={status} onChange={(event) => setStatus(event.target.value as StatusFilter)} className="h-9 rounded-lg border border-[#D0D5DD] bg-white px-3 text-xs"><option value="open">待处理</option><option value="resolved">已解决</option><option value="all">全部状态</option></select>
            <select value={scene} onChange={(event) => setScene(event.target.value)} className="h-9 rounded-lg border border-[#D0D5DD] bg-white px-3 text-xs"><option value="all">全部场景</option>{sceneOptions.map((item) => <option key={item} value={item}>{sceneLabels[item] || item}</option>)}</select>
            <label className="inline-flex h-9 items-center gap-2 rounded-lg border border-[#D0D5DD] px-3 text-xs text-[#475467]"><input type="checkbox" checked={overdueOnly} onChange={(event) => setOverdueOnly(event.target.checked)} className="accent-[#635BFF]" />仅看逾期</label>
          </div>
          {canManage && filteredTasks.length > 0 && (
            <div className="mt-4 space-y-3 border-t border-[#F0F1F3] pt-3 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <label className="mr-2 inline-flex items-center gap-2 text-[#475467]"><input type="checkbox" checked={allVisibleSelected} onChange={toggleVisible} className="accent-[#635BFF]" />全选当前结果</label>
                <span className="text-[#667085]">已选择 {selectedVisibleCount} 项</span>
                <button type="button" disabled={!selectedVisibleCount} onClick={() => setConfirmAction("resolve")} className="ml-auto inline-flex h-8 items-center gap-1.5 rounded-lg bg-[#027A48] px-3 text-white disabled:opacity-40"><CheckCircle2 className="h-3.5 w-3.5" />批量解决</button>
                <button type="button" disabled={!selectedVisibleCount} onClick={() => setConfirmAction("reopen")} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-[#D0D5DD] px-3 text-[#344054] disabled:opacity-40"><RotateCcw className="h-3.5 w-3.5" />批量重开</button>
              </div>
              <div className="flex flex-wrap items-center gap-2 rounded-xl bg-[#F8F9FC] p-3">
                <span className="inline-flex items-center gap-1 font-medium text-[#344054]"><CalendarClock className="h-3.5 w-3.5" />批量调度</span>
                <select aria-label="批量指派负责人" value={bulkAssignee} onChange={(event) => setBulkAssignee(event.target.value)} className="h-8 min-w-[180px] rounded-lg border border-[#D0D5DD] bg-white px-2"><option value="">负责人不修改</option>{members.map((member) => <option key={member.user_id} value={member.user_id}>{member.username} · {member.role}</option>)}</select>
                <input aria-label="批量设置截止时间" type="date" value={bulkDueAt} onChange={(event) => setBulkDueAt(event.target.value)} className="h-8 rounded-lg border border-[#D0D5DD] bg-white px-2" />
                <button type="button" disabled={pending || !selectedVisibleCount || (!bulkAssignee && !bulkDueAt)} onClick={() => void applyBulkAssignment()} className="h-8 rounded-lg bg-[#635BFF] px-3 font-medium text-white disabled:opacity-40">应用负责人/截止时间</button>
              </div>
            </div>
          )}
        </section>

        {error && <div role="alert" className="mt-4 flex items-start justify-between gap-3 rounded-xl border border-[#FDA29B] bg-[#FEF2F2] p-3 text-sm text-[#B42318]"><span>{error}</span><button type="button" onClick={() => setError(null)} aria-label="关闭错误"><X className="h-4 w-4" /></button></div>}
        {notice && <div className="mt-4 rounded-xl border border-[#ABEFC6] bg-[#ECFDF3] p-3 text-sm text-[#027A48]">{notice}</div>}

        {(workspaceLoading || loading) ? <div className="mt-8 flex items-center justify-center gap-2 rounded-2xl border border-dashed border-[#D0D5DD] bg-white py-16 text-sm text-[#667085]"><Loader2 className="h-4 w-4 animate-spin" />正在加载评审任务</div> : filteredTasks.length === 0 && view === "list" ? <div className="mt-8 rounded-2xl border border-dashed border-[#D0D5DD] bg-white py-16 text-center"><ClipboardCheck className="mx-auto h-8 w-8 text-[#98A2B3]" /><p className="mt-3 text-sm font-medium text-[#344054]">当前筛选下没有评审任务</p><p className="mt-1 text-xs text-[#667085]">可以切换状态、责任人或清除搜索条件。</p></div> : view === "list" ? (
          <section className="mt-5 grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
            {filteredTasks.map((task) => <TaskCard key={task.id} task={task} workspaceId={activeWorkspaceId} selected={selectedIds.has(task.id)} selectable={canManage} onToggle={toggleTask} />)}
          </section>
        ) : (
          <section className="mt-5 grid items-start gap-4 xl:grid-cols-4">
            {boardColumns.map((column) => {
              const tasks = filteredTasks.filter((task) => taskGroup(task) === column.key);
              return <div key={column.key} className="rounded-2xl bg-[#F0F1F4] p-3"><div className={`flex items-center justify-between px-1 pb-3 text-sm font-semibold ${column.tone}`}><span>{column.label}</span><span className="rounded-full bg-white px-2 py-0.5 text-xs text-[#475467]">{tasks.length}</span></div><div className="space-y-3">{tasks.map((task) => <TaskCard key={task.id} task={task} workspaceId={activeWorkspaceId} selected={selectedIds.has(task.id)} selectable={canManage} onToggle={toggleTask} />)}{tasks.length === 0 && <p className="rounded-xl border border-dashed border-[#D0D5DD] bg-white/70 px-3 py-8 text-center text-xs text-[#98A2B3]">{column.empty}</p>}</div></div>;
            })}
          </section>
        )}
      </div>

      {confirmAction && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4" role="dialog" aria-modal="true" aria-labelledby="bulk-review-title"><div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"><div className="flex items-start gap-3">{confirmAction === "resolve" ? <CheckCircle2 className="mt-0.5 h-5 w-5 text-[#027A48]" /> : <AlertTriangle className="mt-0.5 h-5 w-5 text-[#B54708]" />}<div><h2 id="bulk-review-title" className="font-semibold">确认批量{confirmAction === "resolve" ? "解决" : "重开"}任务</h2><p className="mt-2 text-sm leading-6 text-[#667085]">将处理当前选中的 {selectedVisibleCount} 项任务，所有状态变化都会写入审计记录并通知相关责任人。</p></div></div><div className="mt-6 flex justify-end gap-2"><button type="button" disabled={pending} onClick={() => setConfirmAction(null)} className="h-9 rounded-lg border border-[#D0D5DD] px-4 text-sm">取消</button><button type="button" disabled={pending || !selectedVisibleCount} onClick={() => void runBulkAction()} className="inline-flex h-9 items-center gap-2 rounded-lg bg-[#635BFF] px-4 text-sm text-white disabled:opacity-50">{pending && <Loader2 className="h-4 w-4 animate-spin" />}确认处理</button></div></div></div>}
    </main>
  );
}
