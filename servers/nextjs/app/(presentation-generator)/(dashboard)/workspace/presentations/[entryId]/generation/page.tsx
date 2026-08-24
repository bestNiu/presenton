"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  FileSearch,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  EnterpriseApi,
  type EnterpriseKnowledgeOutlineResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";

const taskStorageKey = "enterprise.generationTasks";

function forgetGenerationTask(outlineId: string) {
  try {
    const parsed = JSON.parse(localStorage.getItem(taskStorageKey) || "[]");
    if (!Array.isArray(parsed)) return;
    localStorage.setItem(
      taskStorageKey,
      JSON.stringify(parsed.filter((item) => item?.outlineId !== outlineId))
    );
  } catch {
    // A damaged local cache must not block access to the server-side task.
  }
}

export default function EnterpriseGenerationPage() {
  const params = useParams<{ entryId: string }>();
  const searchParams = useSearchParams();
  const entryId = params.entryId;
  const workspaceId = searchParams.get("workspace_id") || "";
  const outlineId = searchParams.get("outline_id") || "";
  const presentationId = searchParams.get("presentation_id") || "";
  const template = searchParams.get("template") || "";
  const [outline, setOutline] = useState<EnterpriseKnowledgeOutlineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!outlineId) {
      setError("缺少生成任务标识，无法恢复任务。");
      setLoading(false);
      setPolling(false);
      return "error";
    }
    try {
      const result = await EnterpriseApi.getKnowledgeOutline(outlineId);
      setOutline(result);
      setError(result.status === "error" ? result.error || "知识大纲生成失败，请重新创建。" : null);
      setLoading(false);
      if (result.status === "ready" || result.status === "error") {
        setPolling(false);
        forgetGenerationTask(outlineId);
      }
      return result.status;
    } catch (cause) {
      setLoading(false);
      setError(cause instanceof Error ? cause.message : "生成任务状态加载失败");
      return "request_error";
    }
  }, [outlineId]);

  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      const status = await load();
      if (!disposed && status !== "ready" && status !== "error") {
        timer = setTimeout(poll, 2500);
      }
    };
    void poll();
    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
    };
  }, [load]);

  const outlineHref = useMemo(() => {
    const destination = new URLSearchParams({ id: presentationId });
    if (template) destination.set("template", template);
    return `/outline?${destination.toString()}`;
  }, [presentationId, template]);
  const status = outline?.status || (loading ? "queued" : "error");
  const slideCount = outline?.outline.slides?.length || 0;
  const progress = status === "ready" ? 100 : status === "generating" ? 68 : status === "queued" ? 24 : 100;

  return (
    <main className="mx-auto w-full max-w-4xl px-5 py-8">
      <Link href={`/workspace/presentations?workspace_id=${encodeURIComponent(workspaceId)}`} className="inline-flex items-center gap-2 text-sm text-[#667085] hover:text-[#344054]">
        <ArrowLeft className="h-4 w-4" />返回文稿中心
      </Link>
      <section className="mt-6 overflow-hidden rounded-2xl border border-[#E4E7EC] bg-white shadow-sm">
        <div className="border-b border-[#EAECF0] bg-[#F8F9FC] px-6 py-5">
          <p className="text-xs font-semibold text-[#635BFF]">企业资料生成任务</p>
          <h1 className="mt-1 text-xl font-semibold text-[#101828]">{outline?.topic || "正在恢复生成任务"}</h1>
          <p className="mt-2 text-sm text-[#667085]">任务信息保存在服务端，可安全刷新或稍后重新打开此页面。</p>
        </div>
        <div className="space-y-6 p-6">
          <div className="flex items-start gap-4">
            <span className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full ${
              status === "ready" ? "bg-[#ECFDF3] text-[#039855]"
                : status === "error" ? "bg-[#FEF3F2] text-[#D92D20]"
                  : "bg-[#F5F3FF] text-[#635BFF]"
            }`}>
              {status === "ready" ? <CheckCircle2 className="h-6 w-6" />
                : status === "error" ? <AlertCircle className="h-6 w-6" />
                  : <Loader2 className="h-6 w-6 animate-spin" />}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="font-semibold text-[#101828]">
                    {status === "ready" ? "大纲已生成"
                      : status === "error" ? "生成未完成"
                        : status === "generating" ? "正在生成可追溯大纲"
                          : "任务已进入生成队列"}
                  </h2>
                  <p className="mt-1 text-sm text-[#667085]">
                    {status === "ready" ? `已生成 ${slideCount || outline?.n_slides || 0} 页结构，可进入大纲确认内容。`
                      : status === "error" ? "可重新检查任务状态，或返回文稿中心重新发起。"
                        : "系统正在检索所选企业资料、组织内容并建立引用关系。"}
                  </p>
                </div>
                {polling && <span className="rounded-full bg-[#F2F4F7] px-2.5 py-1 text-xs text-[#475467]">自动刷新</span>}
              </div>
              <div className="mt-4 h-2 overflow-hidden rounded-full bg-[#EAECF0]">
                <div className={`h-full rounded-full transition-all duration-500 ${status === "error" ? "bg-[#F04438]" : "bg-[#635BFF]"}`} style={{ width: `${progress}%` }} />
              </div>
            </div>
          </div>

          {outline && (
            <dl className="grid gap-3 rounded-xl bg-[#F8F9FC] p-4 text-sm sm:grid-cols-3">
              <div><dt className="text-xs text-[#98A2B3]">目标页数</dt><dd className="mt-1 font-medium text-[#344054]">{outline.n_slides} 页</dd></div>
              <div><dt className="text-xs text-[#98A2B3]">引用资料</dt><dd className="mt-1 font-medium text-[#344054]">{outline.document_ids.length} 份</dd></div>
              <div><dt className="text-xs text-[#98A2B3]">生成语言</dt><dd className="mt-1 font-medium text-[#344054]">{outline.language}</dd></div>
            </dl>
          )}

          {error && <p role="alert" className="rounded-xl bg-[#FEF3F2] p-4 text-sm text-[#B42318]">{error}</p>}

          <div className="flex flex-wrap justify-end gap-3 border-t border-[#EAECF0] pt-5">
            {(status === "error" || error) && (
              <button type="button" onClick={() => { setPolling(true); setError(null); void load(); }} className="inline-flex h-10 items-center gap-2 rounded-lg border border-[#D0D5DD] px-4 text-sm font-medium text-[#344054]">
                <RefreshCw className="h-4 w-4" />重新检查
              </button>
            )}
            {status === "ready" && presentationId && (
              <Link href={outlineHref} className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#635BFF] px-5 text-sm font-medium text-white">
                <FileSearch className="h-4 w-4" />进入大纲确认
              </Link>
            )}
          </div>
        </div>
      </section>
      <p className="mt-4 text-center text-xs text-[#98A2B3]">文稿记录：{entryId} · 生成任务：{outlineId || "未知"}</p>
    </main>
  );
}
