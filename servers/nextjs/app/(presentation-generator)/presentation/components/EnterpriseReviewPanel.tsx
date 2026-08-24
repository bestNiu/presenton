"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, MessageSquare, X } from "lucide-react";

import {
  EnterpriseApi,
  type PresentationCommentThreadResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";

interface EnterpriseReviewPanelProps {
  workspaceId: string;
  entryId: string;
  currentSlideIndex: number;
  currentSlideId?: string;
}

export default function EnterpriseReviewPanel({ workspaceId, entryId, currentSlideIndex, currentSlideId }: EnterpriseReviewPanelProps) {
  const searchParams = useSearchParams();
  const focusedThreadId = searchParams.get("thread_id") || "";
  const [open, setOpen] = useState(Boolean(focusedThreadId));
  const [threads, setThreads] = useState<PresentationCommentThreadResponse[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [blocking, setBlocking] = useState(false);
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({});
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [canComment, setCanComment] = useState(false);

  const load = useCallback(async () => {
    try {
      const [commentRows, workspaces] = await Promise.all([EnterpriseApi.getPresentationComments(workspaceId, entryId), EnterpriseApi.getWorkspaces()]);
      setThreads(commentRows);
      const workspace = workspaces.find((item) => item.id === workspaceId);
      setCanComment(Boolean(workspace && workspace.current_user_role !== "viewer"));
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "评审批注加载失败");
    }
  }, [entryId, workspaceId]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!focusedThreadId) return;
    setOpen(true);
    window.requestAnimationFrame(() => {
      document.getElementById(`canvas-review-thread-${focusedThreadId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }, [focusedThreadId, threads]);

  const currentThreads = useMemo(
    () => threads.filter((thread) => thread.slide_id === null || thread.slide_id === currentSlideId || thread.slide_index === currentSlideIndex),
    [currentSlideId, currentSlideIndex, threads]
  );
  const openCount = currentThreads.filter((thread) => thread.status === "open").length;

  const createThread = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim() || !body.trim()) return;
    setPending(true);
    try {
      await EnterpriseApi.createPresentationComment(workspaceId, entryId, {
        ...(currentSlideId ? { slide_id: currentSlideId } : { slide_index: currentSlideIndex }),
        title: title.trim(), body: body.trim(), is_blocking: blocking,
      });
      setTitle(""); setBody(""); setBlocking(false);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "批注创建失败");
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

  return <>
    <button type="button" onClick={() => setOpen(true)} className="fixed bottom-20 right-5 z-40 inline-flex h-11 items-center gap-2 rounded-full bg-[#17171B] px-4 text-sm font-medium text-white shadow-lg xl:bottom-5 xl:right-[395px]"><MessageSquare className="h-4 w-4" />本页评审{openCount > 0 && <span className="rounded-full bg-[#D92D20] px-1.5 text-[10px]">{openCount}</span>}</button>
    {open && <aside className="fixed inset-y-3 right-3 z-[80] flex w-[min(400px,calc(100vw-24px))] flex-col overflow-hidden rounded-2xl border border-[#E3E4EA] bg-white shadow-2xl">
      <header className="flex items-center justify-between border-b border-[#EAECF0] px-4 py-3"><div><h2 className="text-sm font-semibold text-[#101828]">第 {currentSlideIndex + 1} 页评审</h2><p className="mt-0.5 text-xs text-[#667085]">直接在编辑上下文中闭环整改</p></div><button type="button" onClick={() => setOpen(false)} className="rounded-full p-2 hover:bg-[#F2F4F7]"><X className="h-4 w-4" /></button></header>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        {error && <p className="rounded-lg bg-[#FEF2F2] p-2 text-xs text-[#B42318]">{error}</p>}
        {currentThreads.length === 0 && <p className="rounded-xl bg-[#F8F9FC] p-4 text-center text-xs text-[#667085]">当前页暂无批注</p>}
        {currentThreads.map((thread) => <article id={`canvas-review-thread-${thread.id}`} key={thread.id} className={`rounded-xl border p-3 transition ${thread.id === focusedThreadId ? "border-[#8B7DFF] bg-[#F5F3FF] ring-2 ring-[#E4E1FF]" : "border-[#EAECF0]"}`}><div className="flex items-start justify-between gap-2"><div className="flex gap-2">{thread.is_blocking ? <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#D92D20]" /> : <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#667085]" />}<div><p className="text-sm font-medium text-[#101828]">{thread.title}</p><p className="mt-1 text-xs leading-5 text-[#475467]">{thread.body}</p></div></div><span className={`shrink-0 rounded-full px-2 py-1 text-[10px] ${thread.status === "open" ? "bg-[#FFF4E5] text-[#B54708]" : "bg-[#ECFDF3] text-[#027A48]"}`}>{thread.status === "open" ? "待整改" : "已解决"}</span></div>{thread.replies.map((item) => <p key={item.id} className="mt-2 rounded-lg bg-[#F8F9FC] p-2 text-xs text-[#475467]">{item.body}</p>)}<div className="mt-3 flex gap-2"><input value={replyDrafts[thread.id] || ""} onChange={(event) => setReplyDrafts((current) => ({ ...current, [thread.id]: event.target.value }))} placeholder="回复说明" className="h-8 min-w-0 flex-1 rounded-lg border border-[#D9DCE3] px-2 text-xs" /><button disabled={pending || !replyDrafts[thread.id]?.trim()} onClick={() => void reply(thread.id)} className="rounded-lg bg-[#F2F1FF] px-2 text-xs text-[#4238CA] disabled:opacity-40">回复</button><button disabled={pending} onClick={() => void transition(thread)} className="rounded-lg border border-[#D9DCE3] px-2 text-xs disabled:opacity-40">{thread.status === "open" ? "解决" : "重开"}</button></div></article>)}
      </div>
      <form onSubmit={createThread} className="border-t border-[#EAECF0] p-4">{canComment ? <><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="批注标题" className="h-9 w-full rounded-lg border border-[#D9DCE3] px-3 text-xs" /><textarea value={body} onChange={(event) => setBody(event.target.value)} placeholder="问题说明与整改要求" rows={3} className="mt-2 w-full rounded-lg border border-[#D9DCE3] p-3 text-xs" /><div className="mt-2 flex items-center justify-between"><label className="flex items-center gap-2 text-xs text-[#475467]"><input type="checkbox" checked={blocking} onChange={(event) => setBlocking(event.target.checked)} />阻断审批</label><button disabled={pending || !title.trim() || !body.trim()} className="rounded-lg bg-[#635BFF] px-3 py-2 text-xs text-white disabled:opacity-40">添加到本页</button></div></> : <p className="text-center text-xs text-[#667085]">当前为只读权限，可查看评审批注。</p>}<Link href={`/workspace/presentations/${encodeURIComponent(entryId)}/review?workspace_id=${encodeURIComponent(workspaceId)}`} className="mt-3 block text-center text-xs text-[#635BFF]">打开完整评审中心</Link></form>
    </aside>}
  </>;
}
