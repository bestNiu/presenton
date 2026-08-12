"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Building2,
  FilePlus2,
  FileText,
  FolderKanban,
  LayoutTemplate,
  Loader2,
  MonitorPlay,
  PenLine,
  Plus,
  RefreshCw,
  ShieldCheck,
  Users,
} from "lucide-react";

import {
  EnterpriseApi,
  type ConfidentialityLevel,
  type PresentationEntryResponse,
  type SceneDefinitionResponse,
  type TemplatePublicationResponse,
  type WorkspaceResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";
import { PresentationGenerationApi } from "@/app/(presentation-generator)/services/api/presentation-generation";

const workspaceTypeLabel: Record<WorkspaceResponse["workspace_type"], string> = {
  personal: "个人空间",
  team: "团队空间",
  department: "部门空间",
};

const workspaceRoleLabel: Record<WorkspaceResponse["current_user_role"], string> = {
  owner: "所有者",
  admin: "管理员",
  editor: "编辑者",
  reviewer: "审阅者",
  viewer: "查看者",
};

const creationModeLabel: Record<PresentationEntryResponse["creation_mode"], string> = {
  topic: "主题生成",
  document: "文档生成",
  template: "模板创建",
  blank: "空白创建",
  import: "已有文稿",
};

function WorkspacePage() {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([]);
  const [scenes, setScenes] = useState<SceneDefinitionResponse[]>([]);
  const [presentations, setPresentations] =
    useState<PresentationEntryResponse[]>([]);
  const [publishedTemplates, setPublishedTemplates] =
    useState<TemplatePublicationResponse[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [creatingBlank, setCreatingBlank] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [confidentiality, setConfidentiality] =
    useState<ConfidentialityLevel>("L2");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await EnterpriseApi.ensurePersonalWorkspace();
      const [workspaceRows, sceneRows] = await Promise.all([
        EnterpriseApi.getWorkspaces(),
        EnterpriseApi.getScenes(),
      ]);
      setWorkspaces(workspaceRows);
      setScenes(sceneRows);
      setActiveWorkspaceId((current) => current || workspaceRows[0]?.id || "");
    } catch (loadError) {
      setError(
        loadError instanceof Error ? loadError.message : "工作台加载失败"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!activeWorkspaceId) {
      setPresentations([]);
      setPublishedTemplates([]);
      return;
    }
    let active = true;
    Promise.all([
      EnterpriseApi.getPresentations(activeWorkspaceId),
      EnterpriseApi.getPublishedTemplates(activeWorkspaceId),
    ])
      .then(([presentationRows, templateRows]) => {
        if (active) {
          setPresentations(presentationRows);
          setPublishedTemplates(templateRows);
        }
      })
      .catch((loadError) => {
        if (active) {
          setError(
            loadError instanceof Error ? loadError.message : "文稿列表加载失败"
          );
        }
      });
    return () => {
      active = false;
    };
  }, [activeWorkspaceId]);

  useEffect(() => {
    void load();
  }, [load]);

  const professionalScenes = useMemo(
    () => scenes.filter((scene) => scene.scene_type !== "general"),
    [scenes]
  );

  const activeWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === activeWorkspaceId),
    [activeWorkspaceId, workspaces]
  );
  const canCreate =
    activeWorkspace?.current_user_role === "owner" ||
    activeWorkspace?.current_user_role === "admin" ||
    activeWorkspace?.current_user_role === "editor";

  const buildCreateHref = (entry: "topic" | "document" | "template") => {
    const params = new URLSearchParams({ entry });
    if (activeWorkspaceId) params.set("workspace_id", activeWorkspaceId);
    if (entry === "template") params.set("template", "executive");
    return `/upload?${params.toString()}`;
  };

  const handleCreateBlank = async () => {
    if (!activeWorkspaceId || !canCreate || creatingBlank) return;
    setCreatingBlank(true);
    setError(null);
    try {
      const presentation = await PresentationGenerationApi.createBlankPresentation({
        workspace_id: activeWorkspaceId,
        scene_type: "general",
      });
      router.push(
        `/presentation?id=${encodeURIComponent(presentation.id)}&type=standard`
      );
    } catch (creationError) {
      setError(
        creationError instanceof Error
          ? creationError.message
          : "空白演示文稿创建失败"
      );
    } finally {
      setCreatingBlank(false);
    }
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    const normalizedName = name.trim();
    if (!normalizedName) return;
    setCreating(true);
    setError(null);
    try {
      const workspace = await EnterpriseApi.createWorkspace({
        name: normalizedName,
        workspace_type: "team",
        confidentiality,
      });
      setWorkspaces((current) => [...current, workspace]);
      setActiveWorkspaceId(workspace.id);
      setName("");
      setConfidentiality("L2");
      setShowCreate(false);
    } catch (createError) {
      setError(
        createError instanceof Error ? createError.message : "团队空间创建失败"
      );
    } finally {
      setCreating(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#FBFBFD] px-5 pb-12 pt-8 sm:px-8 lg:px-10">
      <header className="mx-auto flex max-w-[1320px] flex-col gap-5 border-b border-[#E8E8ED] pb-7 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-[#635BFF]">
            <Building2 className="h-4 w-4" />
            企业 PPT 制作中台
          </div>
          <h1 className="font-syne text-3xl font-semibold tracking-[-0.04em] text-[#17171B]">
            工作空间
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#667085]">
            从日常 PPT 快速创建开始，并通过独立场景工作台承载竞标等专业流程。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {activeWorkspaceId && (
            <Link
              href={`/workspace/templates?workspace_id=${encodeURIComponent(activeWorkspaceId)}`}
              className="inline-flex h-10 items-center gap-2 rounded-lg border border-[#D9DCE3] bg-white px-4 text-sm font-medium text-[#344054] transition hover:bg-[#F7F7FA]"
            >
              <LayoutTemplate className="h-4 w-4" />
              模板治理
            </Link>
          )}
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-[#D9DCE3] bg-white px-4 text-sm font-medium text-[#344054] transition hover:bg-[#F7F7FA] disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            刷新
          </button>
          <button
            type="button"
            onClick={() => setShowCreate((value) => !value)}
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#635BFF] px-4 text-sm font-medium text-white transition hover:bg-[#5146E5]"
          >
            <Plus className="h-4 w-4" />
            新建团队空间
          </button>
        </div>
      </header>

      <div className="mx-auto max-w-[1320px]">
        {error && (
          <div className="mt-5 rounded-xl border border-[#FECACA] bg-[#FEF2F2] px-4 py-3 text-sm text-[#B42318]">
            {error}
          </div>
        )}

        {showCreate && (
          <form
            onSubmit={handleCreate}
            className="mt-5 grid gap-3 rounded-2xl border border-[#E3E4EA] bg-white p-5 shadow-sm sm:grid-cols-[1fr_180px_auto]"
          >
            <label className="grid gap-1.5 text-xs font-medium text-[#475467]">
              空间名称
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={200}
                autoFocus
                placeholder="例如：临床运营团队"
                className="h-10 rounded-lg border border-[#D9DCE3] px-3 text-sm text-[#101828] outline-none ring-[#8B7DFF] focus:ring-2"
              />
            </label>
            <label className="grid gap-1.5 text-xs font-medium text-[#475467]">
              默认密级
              <select
                value={confidentiality}
                onChange={(event) =>
                  setConfidentiality(event.target.value as ConfidentialityLevel)
                }
                className="h-10 rounded-lg border border-[#D9DCE3] bg-white px-3 text-sm text-[#101828] outline-none ring-[#8B7DFF] focus:ring-2"
              >
                <option value="L1">L1 公开</option>
                <option value="L2">L2 内部</option>
                <option value="L3">L3 保密</option>
                <option value="L4">L4 严格保密</option>
              </select>
            </label>
            <button
              type="submit"
              disabled={creating || !name.trim()}
              className="mt-auto inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-[#17171B] px-5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {creating && <Loader2 className="h-4 w-4 animate-spin" />}
              创建
            </button>
          </form>
        )}

        <section className="mt-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-base font-semibold text-[#1D2939]">通用 PPT 创建</h2>
              <p className="mt-1 text-sm text-[#667085]">
                选择归属空间后，从四种入口开始；创建记录和审计自动写入空间。
              </p>
            </div>
            <label className="grid gap-1 text-xs font-medium text-[#475467]">
              归属空间
              <select
                value={activeWorkspaceId}
                onChange={(event) => setActiveWorkspaceId(event.target.value)}
                className="h-10 min-w-56 rounded-lg border border-[#D9DCE3] bg-white px-3 text-sm text-[#101828]"
              >
                {workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.name} · {workspace.confidentiality}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {!canCreate && activeWorkspace && (
            <p className="mt-3 rounded-lg bg-[#FFF4E5] px-3 py-2 text-sm text-[#B54708]">
              当前空间角色为{workspaceRoleLabel[activeWorkspace.current_user_role]}，仅可查看文稿。
            </p>
          )}
          <div className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Link
              href={buildCreateHref("topic")}
              onClick={(event) => !canCreate && event.preventDefault()}
              aria-disabled={!canCreate}
              className="group rounded-2xl border border-[#E3E4EA] bg-white p-5 transition hover:-translate-y-0.5 hover:border-[#B9B2FF] hover:shadow-md aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#EEEAFE] text-[#635BFF]">
                <PenLine className="h-5 w-5" />
              </div>
              <h3 className="mt-4 font-semibold text-[#101828]">从主题生成</h3>
              <p className="mt-1 text-sm leading-6 text-[#667085]">
                输入主题、受众和目标，生成可调整的大纲与页面。
              </p>
              <span className="mt-4 flex items-center gap-1 text-sm font-medium text-[#635BFF]">
                开始创建 <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
              </span>
            </Link>
            <Link
              href={buildCreateHref("document")}
              onClick={(event) => !canCreate && event.preventDefault()}
              aria-disabled={!canCreate}
              className="group rounded-2xl border border-[#E3E4EA] bg-white p-5 transition hover:-translate-y-0.5 hover:border-[#B8DEFA] hover:shadow-md aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#EAF6FF] text-[#087BCB]">
                <FileText className="h-5 w-5" />
              </div>
              <h3 className="mt-4 font-semibold text-[#101828]">从文档生成</h3>
              <p className="mt-1 text-sm leading-6 text-[#667085]">
                上传 Word、PDF、表格或已有 PPT，提炼后生成。
              </p>
              <span className="mt-4 flex items-center gap-1 text-sm font-medium text-[#087BCB]">
                上传资料 <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
              </span>
            </Link>
            <Link
              href={buildCreateHref("template")}
              onClick={(event) => !canCreate && event.preventDefault()}
              aria-disabled={!canCreate}
              className="group rounded-2xl border border-[#E3E4EA] bg-white p-5 transition hover:-translate-y-0.5 hover:border-[#A8DADC] hover:shadow-md"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#EAF8F6] text-[#087E8B]">
                <LayoutTemplate className="h-5 w-5" />
              </div>
              <h3 className="mt-4 font-semibold text-[#101828]">从企业模板开始</h3>
              <p className="mt-1 text-sm leading-6 text-[#667085]">
                复用已发布模板，保持字体、色板和版式一致。
              </p>
              <span className="mt-4 flex items-center gap-1 text-sm font-medium text-[#087E8B]">
                选择模板 <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
              </span>
            </Link>
            <button
              type="button"
              onClick={() => void handleCreateBlank()}
              disabled={!canCreate || creatingBlank}
              className="group rounded-2xl border border-[#E3E4EA] bg-white p-5 text-left transition hover:-translate-y-0.5 hover:border-[#F5C9A8] hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FFF1E7] text-[#D86D1C]">
                {creatingBlank ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <FilePlus2 className="h-5 w-5" />
                )}
              </div>
              <h3 className="mt-4 font-semibold text-[#101828]">空白演示文稿</h3>
              <p className="mt-1 text-sm leading-6 text-[#667085]">
                创建一页空白稿，直接进入可视化编辑器自由制作。
              </p>
              <span className="mt-4 flex items-center gap-1 text-sm font-medium text-[#D86D1C]">
                立即编辑 <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
              </span>
            </button>
          </div>
        </section>

        {publishedTemplates.length > 0 && (
          <section className="mt-9">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-[#1D2939]">已发布模板</h2>
                <p className="mt-1 text-sm text-[#667085]">
                  企业级和当前空间授权模板；发布版本不可原地覆盖。
                </p>
              </div>
              <span className="text-sm text-[#667085]">
                {publishedTemplates.length} 个模板
              </span>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {publishedTemplates.map((template) => {
                const params = new URLSearchParams({
                  entry: "template",
                  workspace_id: activeWorkspaceId,
                  template: template.template_id,
                });
                return (
                  <Link
                    key={template.id}
                    href={`/upload?${params.toString()}`}
                    className="rounded-xl border border-[#E3E4EA] bg-white p-4 transition hover:border-[#A8DADC] hover:shadow-sm"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#EAF8F6] text-[#087E8B]">
                        <LayoutTemplate className="h-4 w-4" />
                      </div>
                      {template.is_default && (
                        <span className="rounded-full bg-[#ECFDF3] px-2 py-1 text-[11px] font-medium text-[#027A48]">
                          默认
                        </span>
                      )}
                    </div>
                    <h3 className="mt-3 truncate text-sm font-semibold text-[#101828]">
                      {template.display_name}
                    </h3>
                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#667085]">
                      {template.description || "企业授权模板"}
                    </p>
                    <p className="mt-3 text-xs text-[#98A2B3]">
                      v{template.version} · {template.scope_type}
                    </p>
                  </Link>
                );
              })}
            </div>
          </section>
        )}

        <section className="mt-9">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-[#1D2939]">我的空间</h2>
              <p className="mt-1 text-sm text-[#667085]">
                个人空间用于私有草稿，团队空间用于成员协作和权限管理。
              </p>
            </div>
            <span className="text-sm text-[#667085]">{workspaces.length} 个空间</span>
          </div>
          {loading ? (
            <div className="mt-4 flex h-36 items-center justify-center rounded-2xl border border-dashed border-[#D9DCE3] bg-white text-sm text-[#667085]">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 正在加载空间
            </div>
          ) : (
            <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {workspaces.map((workspace) => (
                <button
                  type="button"
                  key={workspace.id}
                  onClick={() => setActiveWorkspaceId(workspace.id)}
                  className={`rounded-2xl border bg-white p-5 text-left shadow-[0_1px_2px_rgba(16,24,40,0.04)] transition hover:border-[#B9B2FF] ${
                    activeWorkspaceId === workspace.id
                      ? "border-[#8278FF] ring-2 ring-[#EEEAFE]"
                      : "border-[#E3E4EA]"
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#F2F1FF] text-[#635BFF]">
                      {workspace.workspace_type === "personal" ? (
                        <FolderKanban className="h-5 w-5" />
                      ) : (
                        <Users className="h-5 w-5" />
                      )}
                    </div>
                    <span className="rounded-full border border-[#E3E4EA] px-2.5 py-1 text-xs font-medium text-[#475467]">
                      {workspace.confidentiality}
                    </span>
                  </div>
                  <h3 className="mt-4 truncate font-semibold text-[#101828]">
                    {workspace.name}
                  </h3>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-[#667085]">
                    <span>{workspaceTypeLabel[workspace.workspace_type]}</span>
                    <span>·</span>
                    <span>{workspaceRoleLabel[workspace.current_user_role]}</span>
                  </div>
                  <div className="mt-4 flex items-center gap-2 border-t border-[#F0F1F3] pt-4 text-xs text-[#667085]">
                    <ShieldCheck className="h-4 w-4 text-[#12B76A]" />
                    服务端空间权限已启用
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="mt-9">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-[#1D2939]">空间文稿</h2>
              <p className="mt-1 text-sm text-[#667085]">
                {activeWorkspace?.name || "当前空间"}中的通用 PPT 创建记录。
              </p>
            </div>
            <span className="text-sm text-[#667085]">{presentations.length} 份文稿</span>
          </div>
          {presentations.length === 0 ? (
            <div className="mt-4 flex h-28 items-center justify-center rounded-2xl border border-dashed border-[#D9DCE3] bg-white text-sm text-[#667085]">
              当前空间暂无文稿，可从上方四种入口创建
            </div>
          ) : (
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {presentations.slice(0, 9).map((presentation) => (
                <Link
                  key={presentation.id}
                  href={`/presentation?id=${encodeURIComponent(presentation.presentation_id)}&type=standard`}
                  onClick={(event) =>
                    !presentation.can_open && event.preventDefault()
                  }
                  aria-disabled={!presentation.can_open}
                  title={
                    presentation.can_open
                      ? "打开演示文稿"
                      : "当前仅可查看空间元数据，协作编辑授权将在后续切片开放"
                  }
                  className="flex items-center gap-3 rounded-xl border border-[#E3E4EA] bg-white p-4 transition hover:border-[#B9B2FF] hover:shadow-sm aria-disabled:cursor-not-allowed aria-disabled:opacity-60"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#F2F1FF] text-[#635BFF]">
                    <MonitorPlay className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-[#101828]">
                      {presentation.title || "未命名演示文稿"}
                    </p>
                    <p className="mt-1 text-xs text-[#667085]">
                      {creationModeLabel[presentation.creation_mode]} ·{" "}
                      {presentation.can_open ? presentation.status : "仅元数据可见"}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </section>

        <section className="mt-9">
          <h2 className="text-base font-semibold text-[#1D2939]">已注册专业场景</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {professionalScenes.map((scene) => (
              <article
                key={`${scene.scene_type}-${scene.version}`}
                className="rounded-2xl border border-[#E3E4EA] bg-white p-5"
              >
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-semibold text-[#101828]">{scene.display_name}</h3>
                  <span className="rounded-full bg-[#ECFDF3] px-2.5 py-1 text-xs font-medium text-[#027A48]">
                    已启用
                  </span>
                </div>
                <p className="mt-2 text-sm leading-6 text-[#667085]">
                  {scene.description || "专业场景能力"}
                </p>
                <p className="mt-3 text-xs text-[#98A2B3]">场景版本 {scene.version}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

export default WorkspacePage;
