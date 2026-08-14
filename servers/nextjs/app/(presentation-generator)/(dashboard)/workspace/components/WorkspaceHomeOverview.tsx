import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  CheckSquare2,
  FileCheck2,
  FileText,
  LayoutTemplate,
  Library,
  MonitorPlay,
  Shapes,
} from "lucide-react";

import type {
  PresentationEntryResponse,
  PresentationQualityRunResponse,
  PresentationReviewInboxResponse,
  WorkspaceResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";

interface WorkspaceHomeOverviewProps {
  workspace: WorkspaceResponse | undefined;
  workspaceId: string;
  presentations: PresentationEntryResponse[];
  qualityReports: Record<string, PresentationQualityRunResponse | null>;
  reviewInbox: PresentationReviewInboxResponse | null;
  professionalSceneCount: number;
}

function workspaceHref(path: string, workspaceId: string) {
  return workspaceId
    ? `${path}?workspace_id=${encodeURIComponent(workspaceId)}`
    : path;
}

export default function WorkspaceHomeOverview({
  workspace,
  workspaceId,
  presentations,
  qualityReports,
  reviewInbox,
  professionalSceneCount,
}: WorkspaceHomeOverviewProps) {
  const qualityRiskCount = Object.values(qualityReports).filter(
    (report) => report && report.status !== "passed"
  ).length;
  const blockingCount = reviewInbox?.summary.blocking_count || 0;
  const riskCount = blockingCount + qualityRiskCount;
  const canManageDelivery = ["owner", "admin"].includes(
    workspace?.current_user_role || "viewer"
  );

  const metrics = [
    {
      label: "待处理任务",
      value: reviewInbox?.summary.open_count || 0,
      detail: `${reviewInbox?.summary.assigned_to_me_count || 0} 项与我相关`,
      icon: CheckSquare2,
      tone: "bg-[#FFFAEB] text-[#B54708]",
    },
    {
      label: "阻断与风险",
      value: riskCount,
      detail: riskCount ? "需要优先处理" : "当前无阻断项",
      icon: AlertTriangle,
      tone: riskCount
        ? "bg-[#FEF2F2] text-[#B42318]"
        : "bg-[#ECFDF3] text-[#027A48]",
    },
    {
      label: "当前空间文稿",
      value: presentations.length,
      detail: `${presentations.filter((item) => item.status === "draft").length} 份草稿`,
      icon: MonitorPlay,
      tone: "bg-[#F2F1FF] text-[#635BFF]",
    },
    {
      label: "专业场景",
      value: professionalSceneCount,
      detail: "按业务流程独立推进",
      icon: Shapes,
      tone: "bg-[#EAF6FF] text-[#087BCB]",
    },
  ];

  const shortcuts = [
    {
      label: "文档与知识",
      detail: "上传资料、检索与引用",
      href: "/workspace/documents",
      icon: FileText,
      visible: true,
    },
    {
      label: "模板中心",
      detail: "选择和治理企业模板",
      href: "/workspace/templates",
      icon: LayoutTemplate,
      visible: true,
    },
    {
      label: "资产中心",
      detail: "复用页面、图表和素材",
      href: "/workspace/assets",
      icon: Library,
      visible: true,
    },
    {
      label: "交付中心",
      detail: "巡检、授权和撤销交付件",
      href: "/workspace/deliveries",
      icon: FileCheck2,
      visible: canManageDelivery,
    },
  ];

  return (
    <section className="mt-7 grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div>
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-[#1D2939]">今日工作概览</h2>
            <p className="mt-1 text-sm text-[#667085]">
              聚焦待办、风险和最近工作，不在首页堆叠管理配置。
            </p>
          </div>
          <span className="hidden text-xs text-[#98A2B3] sm:block">
            {workspace?.name || "正在加载工作空间"}
          </span>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric) => {
            const Icon = metric.icon;
            return (
              <article
                key={metric.label}
                className="rounded-2xl border border-[#E4E7EC] bg-white p-4 shadow-[0_1px_2px_rgba(16,24,40,0.04)]"
              >
                <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${metric.tone}`}>
                  <Icon className="h-4 w-4" />
                </div>
                <p className="mt-4 text-2xl font-semibold tracking-tight text-[#101828]">
                  {metric.value}
                </p>
                <p className="mt-1 text-sm font-medium text-[#344054]">{metric.label}</p>
                <p className="mt-1 text-xs text-[#98A2B3]">{metric.detail}</p>
              </article>
            );
          })}
        </div>
      </div>

      <div className="rounded-2xl border border-[#E4E7EC] bg-white p-4">
        <h2 className="text-sm font-semibold text-[#1D2939]">快捷入口</h2>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
          {shortcuts.filter((item) => item.visible).map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={workspaceHref(item.href, workspaceId)}
                className="group flex items-center gap-3 rounded-xl border border-transparent px-2.5 py-2 transition hover:border-[#E4E7EC] hover:bg-[#F9FAFB]"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#F2F1FF] text-[#635BFF]">
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-[#344054]">{item.label}</span>
                  <span className="block truncate text-xs text-[#98A2B3]">{item.detail}</span>
                </span>
                <ArrowRight className="h-4 w-4 text-[#98A2B3] transition group-hover:translate-x-0.5" />
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}
