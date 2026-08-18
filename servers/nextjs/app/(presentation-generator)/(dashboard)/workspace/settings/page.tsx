"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  History,
  Loader2,
  Save,
  Settings2,
  ShieldCheck,
  Trash2,
  UserPlus,
  Users,
  X,
} from "lucide-react";

import {
  EnterpriseApi,
  type AuditEventResponse,
  type ConfidentialityLevel,
  type WorkspaceMemberResponse,
  type WorkspaceRole,
} from "@/app/(presentation-generator)/services/api/enterprise";
import { useEnterpriseWorkspace } from "../components/EnterpriseWorkspaceShell";

type EditableRole = Exclude<WorkspaceRole, "owner">;

const roleLabel: Record<WorkspaceRole, string> = {
  owner: "所有者",
  admin: "管理员",
  editor: "编辑者",
  reviewer: "审阅者",
  viewer: "查看者",
};

const roleDescription: Record<EditableRole, string> = {
  admin: "管理成员、策略和空间内容",
  editor: "创建和编辑文稿及内容资源",
  reviewer: "评审文稿、处理整改与批准",
  viewer: "只读查看空间内容和交付结果",
};

const auditActionLabel: Record<string, string> = {
  "workspace.created": "创建工作空间",
  "workspace.details_updated": "更新基本信息",
  "workspace.governance_policy_updated": "更新治理策略",
  "workspace.member_added": "添加成员",
  "workspace.member_role_changed": "调整成员角色",
  "workspace.member_removed": "移除成员",
};

export default function WorkspaceSettingsPage() {
  const {
    activeWorkspace: workspace,
    activeWorkspaceId: workspaceId,
    refreshWorkspaces,
  } = useEnterpriseWorkspace();
  const [name, setName] = useState("");
  const [confidentiality, setConfidentiality] =
    useState<ConfidentialityLevel>("L2");
  const [policy, setPolicy] = useState({
    review_mode: "single" as "none" | "single",
    quality_gate_enabled: true,
    require_numeric_citations: false,
    revoked_delivery_retention_days: 90,
  });
  const [members, setMembers] = useState<WorkspaceMemberResponse[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEventResponse[]>([]);
  const [inviteUsername, setInviteUsername] = useState("");
  const [inviteRole, setInviteRole] = useState<EditableRole>("editor");
  const [removeTarget, setRemoveTarget] =
    useState<WorkspaceMemberResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const canAdmin = ["owner", "admin"].includes(
    workspace?.current_user_role || "viewer"
  );
  const supportsCollaboration = workspace?.workspace_type !== "personal";

  useEffect(() => {
    if (!workspace) return;
    setName(workspace.name);
    setConfidentiality(workspace.confidentiality);
    setPolicy(workspace.governance_policy);
  }, [workspace]);

  const loadWorkspaceManagement = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    setError(null);
    try {
      const memberRows = await EnterpriseApi.getWorkspaceMembers(workspaceId);
      setMembers(memberRows);
      if (canAdmin) {
        setAuditEvents(await EnterpriseApi.getWorkspaceAuditEvents(workspaceId));
      } else {
        setAuditEvents([]);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "工作区设置加载失败");
    } finally {
      setLoading(false);
    }
  }, [canAdmin, workspaceId]);

  useEffect(() => {
    void loadWorkspaceManagement();
  }, [loadWorkspaceManagement]);

  const runAction = async (
    key: string,
    action: () => Promise<void>,
    successMessage: string
  ) => {
    setPending(key);
    setError(null);
    setSuccess(null);
    try {
      await action();
      setSuccess(successMessage);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "操作失败，请稍后重试");
    } finally {
      setPending("");
    }
  };

  const saveDetails = (event: FormEvent) => {
    event.preventDefault();
    if (!workspaceId || !name.trim()) return;
    void runAction(
      "details",
      async () => {
        await EnterpriseApi.updateWorkspace(workspaceId, {
          name: name.trim(),
          confidentiality,
        });
        await refreshWorkspaces();
        await loadWorkspaceManagement();
      },
      "工作空间基本信息已保存"
    );
  };

  const savePolicy = (event: FormEvent) => {
    event.preventDefault();
    if (!workspaceId) return;
    void runAction(
      "policy",
      async () => {
        await EnterpriseApi.updateWorkspaceGovernancePolicy(workspaceId, policy);
        await refreshWorkspaces();
        await loadWorkspaceManagement();
      },
      "治理策略已更新"
    );
  };

  const inviteMember = (event: FormEvent) => {
    event.preventDefault();
    if (!workspaceId || !inviteUsername.trim()) return;
    void runAction(
      "invite",
      async () => {
        await EnterpriseApi.inviteWorkspaceMember(
          workspaceId,
          inviteUsername.trim(),
          inviteRole
        );
        setInviteUsername("");
        await loadWorkspaceManagement();
      },
      "成员已加入工作空间"
    );
  };

  const updateMemberRole = (
    member: WorkspaceMemberResponse,
    role: EditableRole
  ) => {
    if (!workspaceId) return;
    void runAction(
      `role-${member.user_id}`,
      async () => {
        await EnterpriseApi.updateWorkspaceMember(workspaceId, member.user_id, role);
        await loadWorkspaceManagement();
      },
      `${member.username} 的角色已更新`
    );
  };

  const confirmRemoveMember = () => {
    if (!workspaceId || !removeTarget) return;
    const member = removeTarget;
    void runAction(
      `remove-${member.user_id}`,
      async () => {
        await EnterpriseApi.removeWorkspaceMember(workspaceId, member.user_id);
        setRemoveTarget(null);
        await loadWorkspaceManagement();
      },
      `${member.username} 已移出工作空间`
    );
  };

  const orderedMembers = useMemo(
    () =>
      [...members].sort((left, right) => {
        if (left.role === "owner") return -1;
        if (right.role === "owner") return 1;
        return left.username.localeCompare(right.username, "zh-CN");
      }),
    [members]
  );

  return (
    <main className="min-h-screen bg-[#FBFBFD] px-5 py-8 sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1180px]">
        <header className="border-b border-[#E4E7EC] pb-6">
          <p className="flex items-center gap-2 text-sm font-medium text-[#635BFF]">
            <Settings2 className="h-4 w-4" />空间管理
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#101828]">
            工作区设置
          </h1>
          <p className="mt-2 text-sm text-[#667085]">
            管理基本信息、治理规则、成员权限和审计记录。
          </p>
        </header>

        {error && (
          <div className="mt-5 flex items-center gap-2 rounded-xl border border-[#FECACA] bg-[#FEF2F2] px-4 py-3 text-sm text-[#B42318]">
            <AlertTriangle className="h-4 w-4" />{error}
          </div>
        )}
        {success && (
          <div className="mt-5 flex items-center gap-2 rounded-xl border border-[#ABEFC6] bg-[#ECFDF3] px-4 py-3 text-sm text-[#027A48]">
            <CheckCircle2 className="h-4 w-4" />{success}
          </div>
        )}

        {!workspace && loading ? (
          <div className="flex h-64 items-center justify-center text-sm text-[#667085]">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />正在加载工作区设置
          </div>
        ) : (
          <div className="mt-6 grid gap-6">
            <section className="rounded-2xl border border-[#E4E7EC] bg-white p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-base font-semibold text-[#101828]">基本信息</h2>
                  <p className="mt-1 text-sm text-[#667085]">空间名称和默认数据密级。</p>
                </div>
                {!canAdmin && <span className="rounded-full bg-[#F2F4F7] px-2.5 py-1 text-xs text-[#475467]">只读</span>}
              </div>
              <form onSubmit={saveDetails} className="mt-5 grid gap-4 sm:grid-cols-[1fr_220px_auto] sm:items-end">
                <label className="grid gap-1.5 text-xs font-medium text-[#475467]">空间名称<input value={name} onChange={(event) => setName(event.target.value)} disabled={!canAdmin} maxLength={200} className="h-10 rounded-lg border border-[#D0D5DD] px-3 text-sm disabled:bg-[#F9FAFB]" /></label>
                <label className="grid gap-1.5 text-xs font-medium text-[#475467]">默认密级<select value={confidentiality} onChange={(event) => setConfidentiality(event.target.value as ConfidentialityLevel)} disabled={!canAdmin} className="h-10 rounded-lg border border-[#D0D5DD] bg-white px-3 text-sm disabled:bg-[#F9FAFB]"><option value="L1">L1 公开</option><option value="L2">L2 内部</option><option value="L3">L3 保密</option><option value="L4">L4 严格保密</option></select></label>
                {canAdmin && <button type="submit" disabled={pending === "details" || !name.trim()} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-[#635BFF] px-4 text-sm font-medium text-white disabled:opacity-50">{pending === "details" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}保存</button>}
              </form>
            </section>

            <section className="rounded-2xl border border-[#E4E7EC] bg-white p-5">
              <div className="flex items-start justify-between gap-4"><div><h2 className="flex items-center gap-2 text-base font-semibold text-[#101828]"><ShieldCheck className="h-4 w-4 text-[#12B76A]" />治理策略</h2><p className="mt-1 text-sm text-[#667085]">控制评审、质量门禁、引用和撤销件保留。</p></div>{!canAdmin && <span className="rounded-full bg-[#F2F4F7] px-2.5 py-1 text-xs text-[#475467]">只读</span>}</div>
              <form onSubmit={savePolicy} className="mt-5 grid gap-4 md:grid-cols-2">
                <label className="grid gap-1.5 text-xs font-medium text-[#475467]">评审模式<select value={policy.review_mode} onChange={(event) => setPolicy((current) => ({ ...current, review_mode: event.target.value as "none" | "single" }))} disabled={!canAdmin} className="h-10 rounded-lg border border-[#D0D5DD] bg-white px-3 text-sm disabled:bg-[#F9FAFB]"><option value="single">单级审批</option><option value="none">无需审批</option></select></label>
                <label className="grid gap-1.5 text-xs font-medium text-[#475467]">撤销交付件保留天数<input type="number" min={1} max={3650} value={policy.revoked_delivery_retention_days} onChange={(event) => setPolicy((current) => ({ ...current, revoked_delivery_retention_days: Number(event.target.value) }))} disabled={!canAdmin} className="h-10 rounded-lg border border-[#D0D5DD] px-3 text-sm disabled:bg-[#F9FAFB]" /></label>
                <label className="flex items-start gap-3 rounded-xl bg-[#F9FAFB] p-3 text-sm text-[#344054]"><input type="checkbox" checked={policy.quality_gate_enabled} onChange={(event) => setPolicy((current) => ({ ...current, quality_gate_enabled: event.target.checked }))} disabled={!canAdmin} className="mt-1" /><span><span className="block font-medium">启用质量门禁</span><span className="mt-1 block text-xs text-[#667085]">存在阻断问题时禁止冻结和交付。</span></span></label>
                <label className="flex items-start gap-3 rounded-xl bg-[#F9FAFB] p-3 text-sm text-[#344054]"><input type="checkbox" checked={policy.require_numeric_citations} onChange={(event) => setPolicy((current) => ({ ...current, require_numeric_citations: event.target.checked }))} disabled={!canAdmin} className="mt-1" /><span><span className="block font-medium">数字必须提供引用</span><span className="mt-1 block text-xs text-[#667085]">数据型陈述需要绑定可信来源。</span></span></label>
                {canAdmin && <button type="submit" disabled={pending === "policy"} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-[#17171B] px-4 text-sm font-medium text-white disabled:opacity-50 md:col-span-2 md:justify-self-start">{pending === "policy" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}保存治理策略</button>}
              </form>
            </section>

            <section className="rounded-2xl border border-[#E4E7EC] bg-white p-5">
              <div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="flex items-center gap-2 text-base font-semibold text-[#101828]"><Users className="h-4 w-4 text-[#635BFF]" />成员与角色</h2><p className="mt-1 text-sm text-[#667085]">共 {members.length} 名成员；角色变更即时生效并写入审计。</p></div></div>
              {!supportsCollaboration && <div className="mt-4 rounded-xl bg-[#F9FAFB] px-4 py-3 text-sm text-[#667085]">个人空间仅供本人使用。如需协作，请创建团队空间。</div>}
              {canAdmin && supportsCollaboration && <form onSubmit={inviteMember} className="mt-4 grid gap-3 rounded-xl bg-[#F9FAFB] p-4 sm:grid-cols-[1fr_180px_auto] sm:items-end"><label className="grid gap-1.5 text-xs font-medium text-[#475467]">成员用户名<input value={inviteUsername} onChange={(event) => setInviteUsername(event.target.value)} placeholder="输入已注册用户名" className="h-10 rounded-lg border border-[#D0D5DD] bg-white px-3 text-sm" /></label><label className="grid gap-1.5 text-xs font-medium text-[#475467]">初始角色<select value={inviteRole} onChange={(event) => setInviteRole(event.target.value as EditableRole)} className="h-10 rounded-lg border border-[#D0D5DD] bg-white px-3 text-sm">{Object.entries(roleDescription).map(([role, description]) => <option key={role} value={role}>{roleLabel[role as EditableRole]} · {description}</option>)}</select></label><button type="submit" disabled={!inviteUsername.trim() || pending === "invite"} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-[#635BFF] px-4 text-sm font-medium text-white disabled:opacity-50">{pending === "invite" ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}添加成员</button></form>}
              <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[640px] text-left text-sm"><thead className="border-b border-[#EAECF0] text-xs text-[#667085]"><tr><th className="px-3 py-3 font-medium">成员</th><th className="px-3 py-3 font-medium">角色</th><th className="px-3 py-3 font-medium">权限说明</th><th className="px-3 py-3 text-right font-medium">操作</th></tr></thead><tbody>{orderedMembers.map((member) => <tr key={member.id} className="border-b border-[#F2F4F7]"><td className="px-3 py-3"><p className="font-medium text-[#101828]">{member.username}</p><p className="mt-0.5 text-xs text-[#98A2B3]">加入于 {new Date(member.created_at).toLocaleDateString()}</p></td><td className="px-3 py-3">{canAdmin && member.role !== "owner" ? <select value={member.role} onChange={(event) => updateMemberRole(member, event.target.value as EditableRole)} disabled={pending === `role-${member.user_id}`} className="h-9 rounded-lg border border-[#D0D5DD] bg-white px-2 text-sm">{Object.keys(roleDescription).map((role) => <option key={role} value={role}>{roleLabel[role as EditableRole]}</option>)}</select> : <span className="rounded-full bg-[#F2F1FF] px-2.5 py-1 text-xs font-medium text-[#5146E5]">{roleLabel[member.role]}</span>}</td><td className="px-3 py-3 text-xs text-[#667085]">{member.role === "owner" ? "拥有空间全部权限和最终责任" : roleDescription[member.role]}</td><td className="px-3 py-3 text-right">{canAdmin && member.role !== "owner" && <button type="button" onClick={() => setRemoveTarget(member)} className="inline-flex h-8 items-center gap-1 rounded-lg border border-[#FDA29B] px-2.5 text-xs text-[#B42318]"><Trash2 className="h-3.5 w-3.5" />移除</button>}</td></tr>)}</tbody></table></div>
            </section>

            {canAdmin && <section className="rounded-2xl border border-[#E4E7EC] bg-white p-5"><div><h2 className="flex items-center gap-2 text-base font-semibold text-[#101828]"><History className="h-4 w-4 text-[#635BFF]" />最近审计记录</h2><p className="mt-1 text-sm text-[#667085]">展示最近 50 条空间级关键操作。</p></div><div className="mt-4 grid gap-2">{auditEvents.length ? auditEvents.slice(0, 20).map((event) => <article key={event.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#F9FAFB] px-4 py-3"><div><p className="text-sm font-medium text-[#344054]">{auditActionLabel[event.action] || event.action}</p><p className="mt-1 text-xs text-[#98A2B3]">{event.resource_type} · {event.result}</p></div><time className="text-xs text-[#667085]">{new Date(event.created_at).toLocaleString()}</time></article>) : <p className="rounded-xl bg-[#F9FAFB] p-4 text-sm text-[#667085]">暂无审计记录</p>}</div></section>}
          </div>
        )}
      </div>

      {removeTarget && <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/35 p-4"><div role="dialog" aria-modal="true" aria-labelledby="remove-member-title" className="w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl"><div className="flex items-start justify-between gap-4"><div><h2 id="remove-member-title" className="text-base font-semibold text-[#101828]">移除成员</h2><p className="mt-2 text-sm leading-6 text-[#667085]">移除后，{removeTarget.username} 将立即失去该工作空间的访问权限。历史操作记录仍会保留。</p></div><button type="button" onClick={() => setRemoveTarget(null)} className="rounded-lg p-1.5 text-[#667085] hover:bg-[#F2F4F7]" aria-label="关闭"><X className="h-4 w-4" /></button></div><div className="mt-5 flex justify-end gap-2"><button type="button" onClick={() => setRemoveTarget(null)} className="h-9 rounded-lg border border-[#D0D5DD] px-3 text-sm">取消</button><button type="button" onClick={confirmRemoveMember} disabled={pending === `remove-${removeTarget.user_id}`} className="inline-flex h-9 items-center gap-2 rounded-lg bg-[#D92D20] px-3 text-sm text-white disabled:opacity-50">{pending === `remove-${removeTarget.user_id}` && <Loader2 className="h-4 w-4 animate-spin" />}确认移除</button></div></div></div>}
    </main>
  );
}
