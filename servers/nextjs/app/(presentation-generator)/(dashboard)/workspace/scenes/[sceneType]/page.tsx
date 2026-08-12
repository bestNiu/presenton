"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Loader2,
  LockKeyhole,
  Plus,
  ShieldCheck,
} from "lucide-react";

import {
  EnterpriseApi,
  type BidProjectResponse,
  type SceneRuntimeResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";

const policyLabel: Record<string, string> = {
  document_policy: "资料策略",
  workflow_policy: "流程策略",
  quality_policy: "质量策略",
  assembly_policy: "组装策略",
};

function SceneRuntimePage() {
  const params = useParams<{ sceneType: string }>();
  const [runtime, setRuntime] = useState<SceneRuntimeResponse | null>(null);
  const [workspaceId, setWorkspaceId] = useState("");
  const [projects, setProjects] = useState<BidProjectResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [bidCode, setBidCode] = useState("");
  const [projectName, setProjectName] = useState("");
  const [sponsorName, setSponsorName] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const workspaceId = new URLSearchParams(window.location.search).get(
      "workspace_id"
    );
    if (!workspaceId) {
      setError("缺少工作空间，请从企业工作台进入场景。");
      setLoading(false);
      return;
    }
    setWorkspaceId(workspaceId);
    Promise.all([
      EnterpriseApi.getSceneRuntime(params.sceneType, workspaceId),
      params.sceneType === "bid"
        ? EnterpriseApi.getBidProjects(workspaceId)
        : Promise.resolve([]),
    ])
      .then(([runtimeRow, projectRows]) => {
        setRuntime(runtimeRow);
        setProjects(projectRows);
      })
      .catch((cause) =>
        setError(cause instanceof Error ? cause.message : "场景加载失败")
      )
      .finally(() => setLoading(false));
  }, [params.sceneType]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#FBFBFD]">
        <Loader2 className="h-7 w-7 animate-spin text-[#635BFF]" />
      </main>
    );
  }

  if (!runtime || error) {
    return (
      <main className="min-h-screen bg-[#FBFBFD] px-6 py-12">
        <div className="mx-auto max-w-3xl rounded-2xl border border-[#FECACA] bg-white p-7">
          <p className="text-sm text-[#B42318]">{error || "场景不可用"}</p>
          <Link href="/workspace" className="mt-4 inline-flex items-center gap-1 text-sm text-[#635BFF]">
            <ArrowLeft className="h-4 w-4" /> 返回企业工作台
          </Link>
        </div>
      </main>
    );
  }

  const canCreate = runtime.permissions.includes(`${runtime.scene_type}.project.create`);

  const createProject = async (event: FormEvent) => {
    event.preventDefault();
    if (!workspaceId || !bidCode.trim() || !projectName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const project = await EnterpriseApi.createBidProject({
        workspace_id: workspaceId,
        bid_code: bidCode.trim(),
        name: projectName.trim(),
        sponsor_name: sponsorName.trim() || undefined,
        confidentiality: "L3",
      });
      setProjects((current) => [project, ...current]);
      setBidCode("");
      setProjectName("");
      setSponsorName("");
      setShowCreate(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "竞标项目创建失败");
    } finally {
      setCreating(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#F7F8FC] px-5 py-8 sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1240px]">
        <header className="rounded-2xl bg-[#17171B] px-6 py-7 text-white sm:px-8">
          <Link href="/workspace" className="inline-flex items-center gap-1 text-sm text-[#C9C5FF]">
            <ArrowLeft className="h-4 w-4" /> 企业工作台
          </Link>
          <div className="mt-5 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-[#A9A3FF]">
                <ShieldCheck className="h-4 w-4" /> Scene Runtime · v{runtime.version}
              </div>
              <h1 className="font-syne text-3xl font-semibold tracking-[-0.04em]">
                {runtime.display_name}
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#C7C7CF]">
                {runtime.description}
              </p>
            </div>
            <div className="rounded-xl border border-white/15 bg-white/5 px-4 py-3 text-xs text-[#D7D7DE]">
              当前角色：{runtime.workspace_role} · {runtime.create_schema}
            </div>
          </div>
        </header>

        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {runtime.navigation.map((item, index) => (
            <article key={item.code} className="rounded-xl border border-[#E3E4EA] bg-white p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-[#98A2B3]">
                  {String(index + 1).padStart(2, "0")}
                </span>
                {index === 0 ? (
                  <CheckCircle2 className="h-4 w-4 text-[#12B76A]" />
                ) : (
                  <LockKeyhole className="h-4 w-4 text-[#B8BBC5]" />
                )}
              </div>
              <h2 className="mt-5 text-sm font-semibold text-[#101828]">{item.label}</h2>
              <p className="mt-1 text-xs text-[#667085]">能力代码：{item.code}</p>
            </article>
          ))}
        </section>

        <div className="mt-6 grid gap-5 lg:grid-cols-[1.4fr_1fr]">
          <section className="rounded-2xl border border-[#E3E4EA] bg-white p-6">
            <h2 className="font-semibold text-[#101828]">场景运行边界</h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl bg-[#F8F7FF] p-4">
                <p className="text-xs text-[#667085]">直接创建 PPT</p>
                <p className="mt-2 text-sm font-semibold text-[#4238CA]">
                  {runtime.capabilities.direct_presentation_create ? "允许" : "仅通过场景项目组装"}
                </p>
              </div>
              <div className="rounded-xl bg-[#F0F9FF] p-4">
                <p className="text-xs text-[#667085]">场景业务对象</p>
                <p className="mt-2 text-sm font-semibold text-[#175CD3]">
                  {runtime.capabilities.requires_scene_resource ? "必须创建" : "无需创建"}
                </p>
              </div>
            </div>
            <h3 className="mt-6 text-sm font-semibold text-[#344054]">当前权限</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {runtime.permissions.map((permission) => (
                <span key={permission} className="rounded-full bg-[#F2F4F7] px-3 py-1.5 text-xs text-[#475467]">
                  {permission}
                </span>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-[#E3E4EA] bg-white p-6">
            <h2 className="font-semibold text-[#101828]">生效策略</h2>
            <div className="mt-3 divide-y divide-[#EAECF0]">
              {Object.entries(runtime.policies).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between gap-4 py-3 text-sm">
                  <span className="text-[#667085]">{policyLabel[key] || key}</span>
                  <span className="font-medium text-[#344054]">{value}</span>
                </div>
              ))}
            </div>
          </section>
        </div>

        {runtime.scene_type === "bid" && (
          <section className="mt-6 rounded-2xl border border-[#E3E4EA] bg-white p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="font-semibold text-[#101828]">竞标项目</h2>
                <p className="mt-1 text-xs text-[#667085]">
                  项目画像、需求矩阵和策略纸均在项目边界内管理。
                </p>
              </div>
              {canCreate && (
                <button type="button" onClick={() => setShowCreate((value) => !value)} className="inline-flex h-9 items-center justify-center gap-1 rounded-lg bg-[#635BFF] px-3 text-sm font-medium text-white">
                  <Plus className="h-4 w-4" /> 新建竞标项目
                </button>
              )}
            </div>
            {showCreate && (
              <form onSubmit={createProject} className="mt-4 grid gap-3 rounded-xl bg-[#F8F9FC] p-4 md:grid-cols-[160px_1fr_1fr_auto]">
                <input value={bidCode} onChange={(event) => setBidCode(event.target.value)} placeholder="竞标编号" className="h-10 rounded-lg border border-[#D9DCE3] bg-white px-3 text-sm" />
                <input value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="项目名称" className="h-10 rounded-lg border border-[#D9DCE3] bg-white px-3 text-sm" />
                <input value={sponsorName} onChange={(event) => setSponsorName(event.target.value)} placeholder="申办方（可选）" className="h-10 rounded-lg border border-[#D9DCE3] bg-white px-3 text-sm" />
                <button disabled={creating || !bidCode.trim() || !projectName.trim()} className="inline-flex h-10 items-center justify-center gap-1 rounded-lg bg-[#17171B] px-4 text-sm text-white disabled:opacity-50">
                  {creating && <Loader2 className="h-4 w-4 animate-spin" />} 创建
                </button>
              </form>
            )}
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {projects.map((project) => (
                <Link key={project.id} href={`/workspace/scenes/bid/projects/${project.id}`} className="rounded-xl border border-[#E3E4EA] p-4 transition hover:border-[#B9B2FF] hover:shadow-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs font-semibold text-[#635BFF]">{project.bid_code}</span>
                    <span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-[11px] text-[#475467]">{project.status}</span>
                  </div>
                  <h3 className="mt-3 truncate text-sm font-semibold text-[#101828]">{project.name}</h3>
                  <p className="mt-1 text-xs text-[#667085]">{project.sponsor_name || "未填写申办方"} · {project.current_user_role}</p>
                </Link>
              ))}
              {projects.length === 0 && (
                <div className="col-span-full rounded-xl border border-dashed border-[#D9DCE3] py-10 text-center text-sm text-[#667085]">暂无可访问的竞标项目。</div>
              )}
            </div>
          </section>
        )}

        <div className="mt-6 flex flex-col gap-3 rounded-xl border border-[#FEDF89] bg-[#FFFAEB] p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-[#93370D]">
              {runtime.scene_type === "bid" ? "竞标理解主链已接入" : "场景已可直接创建文稿"}
            </p>
            <p className="mt-1 text-xs text-[#B54708]">
              当前已完成配置、权限、策略和通用 PPT 引擎之间的隔离边界。
            </p>
          </div>
          {runtime.scene_type === "bid" ? (
            <button type="button" onClick={() => setShowCreate(true)} disabled={!canCreate} className="inline-flex h-10 items-center justify-center gap-1 rounded-lg bg-[#D97706] px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-45">
              创建场景项目 <ChevronRight className="h-4 w-4" />
            </button>
          ) : null}
        </div>
      </div>
    </main>
  );
}

export default SceneRuntimePage;
