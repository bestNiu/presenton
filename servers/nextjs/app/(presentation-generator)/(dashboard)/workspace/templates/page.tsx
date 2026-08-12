"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2, Loader2, Plus, ShieldCheck } from "lucide-react";

import {
  EnterpriseApi,
  type TemplatePublicationResponse,
  type WorkspaceResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";

const statusLabel: Record<TemplatePublicationResponse["status"], string> = {
  draft: "草稿",
  in_review: "审核中",
  published: "已发布",
  offline: "已下线",
  archived: "已归档",
};

const actionLabel = {
  submit: "提交审核",
  publish: "发布",
  reject: "驳回",
  offline: "下线",
  archive: "归档",
  "set-default": "设为默认",
} as const;

type PublicationAction = keyof typeof actionLabel;

function TemplateGovernancePage() {
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [publications, setPublications] = useState<TemplatePublicationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [actingId, setActingId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [templateId, setTemplateId] = useState("");
  const [publicationKey, setPublicationKey] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [version, setVersion] = useState(1);

  useEffect(() => {
    EnterpriseApi.getWorkspaces()
      .then((rows) => {
        setWorkspaces(rows);
        const requested = new URLSearchParams(window.location.search).get("workspace_id");
        setWorkspaceId(
          rows.some((workspace) => workspace.id === requested)
            ? requested || ""
            : rows[0]?.id || ""
        );
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : "空间加载失败"));
  }, []);

  const loadPublications = useCallback(async () => {
    if (!workspaceId) {
      setPublications([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setPublications(await EnterpriseApi.getTemplatePublications(workspaceId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "模板发布记录加载失败");
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadPublications();
  }, [loadPublications]);

  const workspace = useMemo(
    () => workspaces.find((item) => item.id === workspaceId),
    [workspaceId, workspaces]
  );
  const canEdit = ["owner", "admin", "editor"].includes(
    workspace?.current_user_role || "viewer"
  );
  const canAdmin = ["owner", "admin"].includes(
    workspace?.current_user_role || "viewer"
  );

  const submitPublication = async (event: FormEvent) => {
    event.preventDefault();
    if (!workspaceId || !templateId.trim() || !publicationKey.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await EnterpriseApi.createTemplatePublication({
        template_id: templateId.trim(),
        publication_key: publicationKey.trim(),
        version,
        scope_type: "workspace",
        workspace_id: workspaceId,
        display_name: displayName.trim() || undefined,
        compatibility: { pptx: true },
      });
      setTemplateId("");
      setPublicationKey("");
      setDisplayName("");
      setVersion(1);
      await loadPublications();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "模板版本登记失败");
    } finally {
      setSubmitting(false);
    }
  };

  const runAction = async (
    publication: TemplatePublicationResponse,
    action: PublicationAction
  ) => {
    setActingId(publication.id);
    setError(null);
    try {
      const updated = await EnterpriseApi.transitionTemplatePublication(
        publication.id,
        action
      );
      setPublications((current) =>
        current.map((item) => (item.id === updated.id ? updated : item))
      );
      if (action === "set-default") await loadPublications();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "状态更新失败");
    } finally {
      setActingId("");
    }
  };

  const actionsFor = (publication: TemplatePublicationResponse): PublicationAction[] => {
    if (publication.status === "draft") {
      return canEdit ? ["submit", ...(canAdmin ? (["archive"] as const) : [])] : [];
    }
    if (!canAdmin) return [];
    if (publication.status === "in_review") return ["publish", "reject"];
    if (publication.status === "published") {
      return publication.is_default ? ["offline"] : ["set-default", "offline"];
    }
    if (publication.status === "offline") return ["archive"];
    return [];
  };

  return (
    <main className="min-h-screen bg-[#FBFBFD] px-5 py-8 sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1180px]">
        <header className="flex flex-col gap-4 border-b border-[#E8E8ED] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <Link href="/workspace" className="mb-3 inline-flex items-center gap-1 text-sm text-[#635BFF]">
              <ArrowLeft className="h-4 w-4" /> 返回工作台
            </Link>
            <h1 className="font-syne text-3xl font-semibold tracking-[-0.04em] text-[#17171B]">
              模板发布治理
            </h1>
            <p className="mt-2 text-sm text-[#667085]">
              管理空间模板的版本、审核、发布、默认版本和下线归档。
            </p>
          </div>
          <label className="grid gap-1 text-xs font-medium text-[#475467]">
            工作空间
            <select
              value={workspaceId}
              onChange={(event) => setWorkspaceId(event.target.value)}
              className="h-10 min-w-60 rounded-lg border border-[#D9DCE3] bg-white px-3 text-sm"
            >
              {workspaces.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </label>
        </header>

        {error && (
          <div className="mt-5 rounded-xl border border-[#FECACA] bg-[#FEF2F2] px-4 py-3 text-sm text-[#B42318]">
            {error}
          </div>
        )}

        {canEdit && (
          <form onSubmit={submitPublication} className="mt-6 rounded-2xl border border-[#E3E4EA] bg-white p-5">
            <div className="flex items-center gap-2">
              <Plus className="h-4 w-4 text-[#635BFF]" />
              <h2 className="font-semibold text-[#101828]">登记新模板版本</h2>
            </div>
            <p className="mt-1 text-xs text-[#667085]">
              请先在自定义模板流程完成版式生成；登记时自动校验布局、预览和 PPTX 兼容性。
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-[1.3fr_1fr_1fr_100px_auto]">
              <input value={templateId} onChange={(event) => setTemplateId(event.target.value)} placeholder="模板 ID" className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm" />
              <input value={publicationKey} onChange={(event) => setPublicationKey(event.target.value)} placeholder="发布标识，如 brand-report" className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm" />
              <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="展示名称（可选）" className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm" />
              <input type="number" min={1} value={version} onChange={(event) => setVersion(Number(event.target.value) || 1)} aria-label="版本号" className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm" />
              <button disabled={submitting || !templateId.trim() || !publicationKey.trim()} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-[#635BFF] px-4 text-sm font-medium text-white disabled:opacity-50">
                {submitting && <Loader2 className="h-4 w-4 animate-spin" />} 登记
              </button>
            </div>
          </form>
        )}

        <section className="mt-7">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold text-[#101828]">版本记录</h2>
            <span className="text-xs text-[#667085]">{publications.length} 条</span>
          </div>
          {loading ? (
            <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-[#635BFF]" /></div>
          ) : publications.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[#D9DCE3] bg-white py-14 text-center text-sm text-[#667085]">
              当前空间还没有可见的模板发布记录。
            </div>
          ) : (
            <div className="grid gap-3">
              {publications.map((publication) => (
                <article key={publication.id} className="flex flex-col gap-4 rounded-xl border border-[#E3E4EA] bg-white p-4 md:flex-row md:items-center md:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold text-[#101828]">{publication.display_name}</h3>
                      <span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-[11px] text-[#475467]">{statusLabel[publication.status]}</span>
                      {publication.is_default && <span className="inline-flex items-center gap-1 rounded-full bg-[#ECFDF3] px-2 py-1 text-[11px] text-[#027A48]"><CheckCircle2 className="h-3 w-3" /> 默认</span>}
                    </div>
                    <p className="mt-1 truncate text-xs text-[#667085]">{publication.publication_key} · v{publication.version} · {publication.template_id}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {actionsFor(publication).map((action) => (
                      <button key={action} type="button" disabled={actingId === publication.id} onClick={() => void runAction(publication, action)} className="inline-flex h-9 items-center gap-1 rounded-lg border border-[#D9DCE3] px-3 text-xs font-medium text-[#344054] hover:bg-[#F7F7FA] disabled:opacity-50">
                        {actingId === publication.id && <Loader2 className="h-3 w-3 animate-spin" />}{actionLabel[action]}
                      </button>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <div className="mt-7 flex items-start gap-3 rounded-xl bg-[#F0F9FF] p-4 text-sm text-[#175CD3]">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
          已发布过的模板版本永久只读；需要调整品牌或布局时，请复制为新的模板 ID 并递增版本号。
        </div>
      </div>
    </main>
  );
}

export default TemplateGovernancePage;
