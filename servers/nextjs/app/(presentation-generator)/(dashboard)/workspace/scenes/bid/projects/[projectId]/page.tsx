"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertTriangle, ArrowLeft, CheckCircle2, FileText, Loader2, Target } from "lucide-react";

import {
  EnterpriseApi,
  type BidProjectDashboardResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";

const statusLabel = {
  understanding: "项目理解",
  strategy_pending: "策略待确认",
  strategy_confirmed: "策略已确认",
  archived: "已归档",
};

function BidProjectDashboardPage() {
  const params = useParams<{ projectId: string }>();
  const [dashboard, setDashboard] = useState<BidProjectDashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    EnterpriseApi.getBidProject(params.projectId)
      .then(setDashboard)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "项目加载失败"));
  }, [params.projectId]);

  if (!dashboard && !error) {
    return <main className="flex min-h-screen items-center justify-center bg-[#F7F8FC]"><Loader2 className="h-7 w-7 animate-spin text-[#635BFF]" /></main>;
  }
  if (!dashboard) {
    return <main className="min-h-screen bg-[#F7F8FC] p-8"><div className="mx-auto max-w-4xl rounded-xl border border-[#FECACA] bg-white p-6 text-sm text-[#B42318]">{error}</div></main>;
  }

  const { project, profile, documents, requirements, strategy } = dashboard;
  const activeDocuments = documents.filter((document) => document.status === "active");

  return (
    <main className="min-h-screen bg-[#F7F8FC] px-5 py-8 sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1240px]">
        <header className="rounded-2xl bg-white p-6 shadow-sm">
          <Link href={`/workspace/scenes/bid?workspace_id=${project.workspace_id}`} className="inline-flex items-center gap-1 text-sm text-[#635BFF]"><ArrowLeft className="h-4 w-4" /> 竞标工作台</Link>
          <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold text-[#635BFF]">{project.bid_code}</p>
              <h1 className="mt-1 font-syne text-3xl font-semibold tracking-[-0.04em] text-[#17171B]">{project.name}</h1>
              <p className="mt-2 text-sm text-[#667085]">{project.sponsor_name || "未填写申办方"} · {project.drug_name || "药物待确认"} · {project.indication || "适应症待确认"}</p>
            </div>
            <span className="rounded-full bg-[#F2F1FF] px-3 py-1.5 text-xs font-medium text-[#4238CA]">{statusLabel[project.status]}</span>
          </div>
        </header>

        <section className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="资料有效版本" value={String(activeDocuments.length)} detail="RFP 与方案资料影响策略门禁" />
          <Metric label="画像状态" value={profile.status === "confirmed" ? "已确认" : "待确认"} detail={`${Object.keys(profile.facts).length} 个结构化字段`} />
          <Metric label="必答覆盖率" value={`${dashboard.mandatory_requirement_coverage}%`} detail={`${requirements.filter((item) => item.mandatory).length} 个必答项`} />
          <Metric label="策略纸" value={strategy.status === "confirmed" ? "已确认" : `v${strategy.version_no} 草稿`} detail="确认后开放专业模块" />
        </section>

        <div className="mt-5 grid gap-5 lg:grid-cols-[1.25fr_1fr]">
          <section className="rounded-2xl border border-[#E3E4EA] bg-white p-6">
            <div className="flex items-center gap-2"><Target className="h-4 w-4 text-[#635BFF]" /><h2 className="font-semibold text-[#101828]">策略确认门禁</h2></div>
            {dashboard.strategy_blockers.length === 0 ? (
              <div className="mt-4 flex items-center gap-2 rounded-xl bg-[#ECFDF3] p-4 text-sm text-[#027A48]"><CheckCircle2 className="h-4 w-4" /> 所有前置检查均已通过</div>
            ) : (
              <div className="mt-4 grid gap-2">
                {dashboard.strategy_blockers.map((blocker) => <div key={blocker} className="flex items-start gap-2 rounded-lg bg-[#FFFAEB] px-3 py-2.5 text-sm text-[#B54708]"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{blocker}</div>)}
              </div>
            )}
          </section>
          <section className="rounded-2xl border border-[#E3E4EA] bg-white p-6">
            <div className="flex items-center gap-2"><FileText className="h-4 w-4 text-[#087BCB]" /><h2 className="font-semibold text-[#101828]">项目资料</h2></div>
            <div className="mt-3 divide-y divide-[#EAECF0]">
              {activeDocuments.map((document) => <div key={document.id} className="flex items-center justify-between py-3 text-sm"><span className="truncate text-[#344054]">{document.logical_name}</span><span className="text-xs text-[#667085]">{document.category} · v{document.version_no}</span></div>)}
              {activeDocuments.length === 0 && <p className="py-6 text-center text-sm text-[#98A2B3]">尚未登记项目资料</p>}
            </div>
          </section>
        </div>

        <section className="mt-5 rounded-2xl border border-[#E3E4EA] bg-white p-6">
          <h2 className="font-semibold text-[#101828]">需求矩阵</h2>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="text-xs text-[#667085]"><tr><th className="pb-3">类别</th><th className="pb-3">客户原文</th><th className="pb-3">必答</th><th className="pb-3">责任部门</th><th className="pb-3">目标模块</th><th className="pb-3">状态</th></tr></thead>
              <tbody className="divide-y divide-[#EAECF0]">{requirements.map((item) => <tr key={item.id}><td className="py-3 text-[#475467]">{item.category}</td><td className="max-w-sm py-3 text-[#101828]">{item.original_text}</td><td className="py-3">{item.mandatory ? "是" : "否"}</td><td className="py-3 text-[#667085]">{item.owner_department || "未认领"}</td><td className="py-3 text-[#667085]">{item.target_module || "待分配"}</td><td className="py-3"><span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-xs">{item.status}</span></td></tr>)}</tbody>
            </table>
            {requirements.length === 0 && <p className="py-8 text-center text-sm text-[#98A2B3]">尚未录入或抽取需求</p>}
          </div>
        </section>
      </div>
    </main>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <article className="rounded-xl border border-[#E3E4EA] bg-white p-4"><p className="text-xs text-[#667085]">{label}</p><p className="mt-2 text-xl font-semibold text-[#101828]">{value}</p><p className="mt-1 text-xs text-[#98A2B3]">{detail}</p></article>;
}

export default BidProjectDashboardPage;
