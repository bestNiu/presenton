"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Bell,
  Boxes,
  FileCheck2,
  FileText,
  LayoutDashboard,
  LayoutTemplate,
  Library,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
  ShieldCheck,
} from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  EnterpriseApi,
  type WorkspaceResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";

const ACTIVE_WORKSPACE_KEY = "enterprise.activeWorkspaceId";

interface EnterpriseWorkspaceContextValue {
  workspaces: WorkspaceResponse[];
  activeWorkspace: WorkspaceResponse | null;
  activeWorkspaceId: string;
  loading: boolean;
  error: string | null;
  setActiveWorkspaceId: (workspaceId: string) => void;
  refreshWorkspaces: () => Promise<void>;
}

const EnterpriseWorkspaceContext =
  createContext<EnterpriseWorkspaceContextValue | null>(null);

export function useEnterpriseWorkspace() {
  const context = useContext(EnterpriseWorkspaceContext);
  if (!context) {
    throw new Error(
      "useEnterpriseWorkspace must be used inside EnterpriseWorkspaceShell"
    );
  }
  return context;
}

const roleLabel: Record<WorkspaceResponse["current_user_role"], string> = {
  owner: "所有者",
  admin: "管理员",
  editor: "编辑者",
  reviewer: "审阅者",
  viewer: "查看者",
};

const navigation: Array<{
  label: string;
  href: string;
  icon: typeof LayoutDashboard;
  adminOnly?: boolean;
}> = [
  { label: "工作台总览", href: "/workspace", icon: LayoutDashboard },
  { label: "文档与知识", href: "/workspace/documents", icon: FileText },
  { label: "模板中心", href: "/workspace/templates", icon: LayoutTemplate },
  { label: "资产中心", href: "/workspace/assets", icon: Library },
  {
    label: "交付中心",
    href: "/workspace/deliveries",
    icon: FileCheck2,
    adminOnly: true,
  },
];

function withWorkspace(href: string, workspaceId: string) {
  return workspaceId
    ? `${href}?workspace_id=${encodeURIComponent(workspaceId)}`
    : href;
}

export default function EnterpriseWorkspaceShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceIdState] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshWorkspaces = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await EnterpriseApi.ensurePersonalWorkspace();
      const rows = await EnterpriseApi.getWorkspaces();
      const requested = new URLSearchParams(window.location.search).get(
        "workspace_id"
      );
      const remembered = window.localStorage.getItem(ACTIVE_WORKSPACE_KEY);
      const nextId =
        [requested, remembered].find(
          (candidate) =>
            candidate && rows.some((workspace) => workspace.id === candidate)
        ) || rows[0]?.id || "";
      setWorkspaces(rows);
      setActiveWorkspaceIdState(nextId);
      if (nextId) window.localStorage.setItem(ACTIVE_WORKSPACE_KEY, nextId);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "工作空间上下文加载失败"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshWorkspaces();
    // The initial request resolves URL and local-storage state itself. Running
    // again for the selected id would duplicate workspace initialization.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectWorkspace = useCallback(
    (workspaceId: string) => {
      setActiveWorkspaceIdState(workspaceId);
      window.localStorage.setItem(ACTIVE_WORKSPACE_KEY, workspaceId);
      const resourceRoute =
        pathname.includes("/projects/") || pathname.includes("/presentations/");
      const targetPath = resourceRoute ? "/workspace" : pathname;
      router.push(withWorkspace(targetPath, workspaceId));
    },
    [pathname, router]
  );

  const activeWorkspace = useMemo(
    () =>
      workspaces.find((workspace) => workspace.id === activeWorkspaceId) || null,
    [activeWorkspaceId, workspaces]
  );

  const contextValue = useMemo<EnterpriseWorkspaceContextValue>(
    () => ({
      workspaces,
      activeWorkspace,
      activeWorkspaceId,
      loading,
      error,
      setActiveWorkspaceId: selectWorkspace,
      refreshWorkspaces,
    }),
    [
      activeWorkspace,
      activeWorkspaceId,
      error,
      loading,
      refreshWorkspaces,
      selectWorkspace,
      workspaces,
    ]
  );

  return (
    <EnterpriseWorkspaceContext.Provider value={contextValue}>
      <div className="min-h-screen bg-[#F7F7FA]">
        <div className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-[#E4E7EC] bg-white/95 px-4 backdrop-blur sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setCollapsed((value) => !value)}
              className="hidden rounded-lg border border-[#E4E7EC] p-2 text-[#475467] hover:bg-[#F9FAFB] lg:inline-flex"
              aria-label={collapsed ? "展开企业导航" : "收起企业导航"}
            >
              {collapsed ? (
                <PanelLeftOpen className="h-4 w-4" />
              ) : (
                <PanelLeftClose className="h-4 w-4" />
              )}
            </button>
            <div className="hidden items-center gap-2 text-sm font-semibold text-[#101828] sm:flex">
              <Boxes className="h-5 w-5 text-[#635BFF]" />
              企业 PPT 制作中台
            </div>
            <span className="hidden text-[#D0D5DD] sm:inline">/</span>
            <label className="flex min-w-0 items-center gap-2">
              <span className="sr-only">当前工作空间</span>
              {loading ? (
                <span className="inline-flex items-center gap-2 text-sm text-[#667085]">
                  <Loader2 className="h-4 w-4 animate-spin" />加载空间
                </span>
              ) : (
                <select
                  value={activeWorkspaceId}
                  onChange={(event) => selectWorkspace(event.target.value)}
                  disabled={!workspaces.length}
                  className="h-9 max-w-[240px] rounded-lg border border-[#D0D5DD] bg-white px-3 text-sm font-medium text-[#344054] outline-none focus:border-[#8B7DFF] disabled:opacity-60"
                >
                  {!workspaces.length && <option value="">暂无工作空间</option>}
                  {workspaces.map((workspace) => (
                    <option key={workspace.id} value={workspace.id}>
                      {workspace.name}
                    </option>
                  ))}
                </select>
              )}
            </label>
            {activeWorkspace && (
              <span className="hidden rounded-full bg-[#F2F4F7] px-2.5 py-1 text-xs text-[#475467] md:inline-flex">
                {roleLabel[activeWorkspace.current_user_role]}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {error && (
              <button
                type="button"
                onClick={() => void refreshWorkspaces()}
                className="hidden text-xs text-[#B42318] sm:inline"
              >
                空间加载失败，点击重试
              </button>
            )}
            <Link
              href={withWorkspace("/workspace", activeWorkspaceId)}
              className="relative rounded-lg border border-[#E4E7EC] p-2 text-[#475467] hover:bg-[#F9FAFB]"
              aria-label="查看通知"
            >
              <Bell className="h-4 w-4" />
            </Link>
            <span className="hidden items-center gap-1.5 rounded-full bg-[#ECFDF3] px-2.5 py-1 text-xs font-medium text-[#027A48] sm:inline-flex">
              <ShieldCheck className="h-3.5 w-3.5" />治理已启用
            </span>
          </div>
        </div>

        <div className="flex min-w-0">
          <aside
            className={`sticky top-16 hidden h-[calc(100vh-4rem)] shrink-0 border-r border-[#E4E7EC] bg-white px-3 py-5 transition-[width] lg:block ${collapsed ? "w-[72px]" : "w-[210px]"}`}
          >
            <nav className="space-y-1" aria-label="企业中台导航">
              {navigation
                .filter(
                  (item) =>
                    !item.adminOnly ||
                    ["owner", "admin"].includes(
                      activeWorkspace?.current_user_role || "viewer"
                    )
                )
                .map((item) => {
                const Icon = item.icon;
                const active =
                  item.href === "/workspace"
                    ? pathname === "/workspace"
                    : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={withWorkspace(item.href, activeWorkspaceId)}
                    title={item.label}
                    className={`flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium transition ${
                      active
                        ? "bg-[#F0EEFF] text-[#5146E5]"
                        : "text-[#475467] hover:bg-[#F9FAFB] hover:text-[#101828]"
                    }`}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {!collapsed && <span>{item.label}</span>}
                  </Link>
                );
                })}
            </nav>
          </aside>
          <div className="min-w-0 flex-1">{children}</div>
        </div>
      </div>
    </EnterpriseWorkspaceContext.Provider>
  );
}
