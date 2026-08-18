"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  FileText,
  Folder,
  FolderPlus,
  Loader2,
  Pencil,
  Search,
  X,
} from "lucide-react";

import {
  EnterpriseApi,
  type FolderResponse,
  type PresentationCreationMode,
  type PresentationEntryResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";
import { useEnterpriseWorkspace } from "../components/EnterpriseWorkspaceShell";

const creationModeLabel: Record<PresentationCreationMode, string> = {
  topic: "主题生成",
  document: "文档生成",
  template: "模板创建",
  blank: "空白创建",
  import: "已有文稿",
};

const statusLabel: Record<PresentationEntryResponse["status"], string> = {
  draft: "草稿",
  in_review: "评审中",
  approved: "已批准",
  frozen: "已冻结",
  published: "已发布",
  archived: "已归档",
};

interface FolderRow extends FolderResponse {
  depth: number;
}

function flattenFolders(folders: FolderResponse[]): FolderRow[] {
  const children = new Map<string | null, FolderResponse[]>();
  for (const folder of folders) {
    const rows = children.get(folder.parent_id) || [];
    rows.push(folder);
    children.set(folder.parent_id, rows);
  }
  for (const rows of children.values()) {
    rows.sort((left, right) => left.name.localeCompare(right.name, "zh-CN"));
  }
  const result: FolderRow[] = [];
  const visit = (parentId: string | null, depth: number) => {
    for (const folder of children.get(parentId) || []) {
      result.push({ ...folder, depth });
      visit(folder.id, depth + 1);
    }
  };
  visit(null, 0);
  return result;
}

export default function WorkspacePresentationsPage() {
  const { activeWorkspace: workspace, activeWorkspaceId: workspaceId } =
    useEnterpriseWorkspace();
  const [folders, setFolders] = useState<FolderResponse[]>([]);
  const [presentations, setPresentations] = useState<PresentationEntryResponse[]>([]);
  const [activeFolder, setActiveFolder] = useState<"all" | "root" | string>("all");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [creationMode, setCreationMode] = useState("all");
  const [selected, setSelected] = useState<string[]>([]);
  const [moveTarget, setMoveTarget] = useState("root");
  const [folderDialog, setFolderDialog] = useState<FolderResponse | "create" | null>(null);
  const [folderName, setFolderName] = useState("");
  const [folderParent, setFolderParent] = useState("root");
  const [archiveTarget, setArchiveTarget] = useState<FolderResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const canEdit = ["owner", "admin", "editor"].includes(
    workspace?.current_user_role || "viewer"
  );

  const load = useCallback(async () => {
    if (!workspaceId) {
      setFolders([]);
      setPresentations([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [folderRows, presentationRows] = await Promise.all([
        EnterpriseApi.getFolders(workspaceId),
        EnterpriseApi.getPresentations(workspaceId),
      ]);
      setFolders(folderRows);
      setPresentations(presentationRows);
      setSelected([]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "文稿中心加载失败");
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void load();
  }, [load]);

  const folderRows = useMemo(() => flattenFolders(folders), [folders]);
  const folderNames = useMemo(
    () => new Map(folders.map((folder) => [folder.id, folder.name])),
    [folders]
  );
  const unavailableParentIds = useMemo(() => {
    if (!folderDialog || folderDialog === "create") return new Set<string>();
    const parentById = new Map(
      folders.map((folder) => [folder.id, folder.parent_id])
    );
    return new Set(
      folders
        .filter((candidate) => {
          let parentId: string | null = candidate.id;
          while (parentId) {
            if (parentId === folderDialog.id) return true;
            parentId = parentById.get(parentId) || null;
          }
          return false;
        })
        .map((folder) => folder.id)
    );
  }, [folderDialog, folders]);
  const folderCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of presentations) {
      if (item.folder_id) counts.set(item.folder_id, (counts.get(item.folder_id) || 0) + 1);
    }
    return counts;
  }, [presentations]);

  const visiblePresentations = useMemo(() => {
    const keyword = search.trim().toLocaleLowerCase("zh-CN");
    return presentations.filter((item) => {
      if (activeFolder === "root" && item.folder_id !== null) return false;
      if (activeFolder !== "all" && activeFolder !== "root" && item.folder_id !== activeFolder) return false;
      if (status !== "all" && item.status !== status) return false;
      if (creationMode !== "all" && item.creation_mode !== creationMode) return false;
      return !keyword || (item.title || "未命名文稿").toLocaleLowerCase("zh-CN").includes(keyword);
    });
  }, [activeFolder, creationMode, presentations, search, status]);

  const runAction = async (
    key: string,
    action: () => Promise<void>,
    message: string
  ) => {
    setPending(key);
    setError(null);
    setSuccess(null);
    try {
      await action();
      setSuccess(message);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "操作失败，请稍后重试");
    } finally {
      setPending("");
    }
  };

  const openCreateFolder = () => {
    setFolderName("");
    setFolderParent(activeFolder !== "all" && activeFolder !== "root" ? activeFolder : "root");
    setFolderDialog("create");
  };

  const openEditFolder = (folder: FolderResponse) => {
    setFolderName(folder.name);
    setFolderParent(folder.parent_id || "root");
    setFolderDialog(folder);
  };

  const saveFolder = (event: FormEvent) => {
    event.preventDefault();
    if (!workspaceId || !folderDialog || !folderName.trim()) return;
    const editing = folderDialog !== "create";
    void runAction(
      "folder",
      async () => {
        const input = {
          name: folderName.trim(),
          parent_id: folderParent === "root" ? null : folderParent,
        };
        if (editing) {
          await EnterpriseApi.updateFolder(workspaceId, folderDialog.id, input);
        } else {
          await EnterpriseApi.createFolder(workspaceId, input);
        }
        setFolderDialog(null);
        await load();
      },
      editing ? "文件夹已更新" : "文件夹已创建"
    );
  };

  const archiveFolder = () => {
    if (!workspaceId || !archiveTarget) return;
    const target = archiveTarget;
    void runAction(
      "archive",
      async () => {
        await EnterpriseApi.archiveFolder(workspaceId, target.id);
        if (activeFolder === target.id) setActiveFolder("all");
        setArchiveTarget(null);
        await load();
      },
      "文件夹已归档"
    );
  };

  const movePresentations = () => {
    if (!workspaceId || !selected.length) return;
    void runAction(
      "move",
      async () => {
        await EnterpriseApi.movePresentations(
          workspaceId,
          selected,
          moveTarget === "root" ? null : moveTarget
        );
        await load();
      },
      `已移动 ${selected.length} 份文稿`
    );
  };

  const allVisibleSelected =
    visiblePresentations.length > 0 &&
    visiblePresentations.every((item) => selected.includes(item.id));

  return (
    <main className="min-h-screen bg-[#FBFBFD] px-5 py-8 sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1280px]">
        <header className="flex flex-col gap-4 border-b border-[#E4E7EC] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="flex items-center gap-2 text-sm font-medium text-[#635BFF]">
              <FileText className="h-4 w-4" />内容生产
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#101828]">文稿中心</h1>
            <p className="mt-2 text-sm text-[#667085]">集中检索、分类和维护工作空间内的全部 PPT 文稿。</p>
          </div>
          {canEdit && (
            <button type="button" onClick={openCreateFolder} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-[#635BFF] px-4 text-sm font-medium text-white hover:bg-[#5147E5]">
              <FolderPlus className="h-4 w-4" />新建文件夹
            </button>
          )}
        </header>

        {error && <div className="mt-5 flex items-center gap-2 rounded-xl border border-[#FECACA] bg-[#FEF2F2] px-4 py-3 text-sm text-[#B42318]"><AlertTriangle className="h-4 w-4 shrink-0" />{error}</div>}
        {success && <div className="mt-5 flex items-center gap-2 rounded-xl border border-[#ABEFC6] bg-[#ECFDF3] px-4 py-3 text-sm text-[#027A48]"><CheckCircle2 className="h-4 w-4 shrink-0" />{success}</div>}

        {loading ? (
          <div className="flex h-72 items-center justify-center text-sm text-[#667085]"><Loader2 className="mr-2 h-5 w-5 animate-spin" />正在加载文稿中心</div>
        ) : (
          <div className="mt-6 grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
            <aside className="h-fit rounded-2xl border border-[#E4E7EC] bg-white p-3">
              <div className="px-2 pb-2 text-xs font-semibold uppercase tracking-wide text-[#98A2B3]">文件夹</div>
              <button type="button" onClick={() => setActiveFolder("all")} className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm ${activeFolder === "all" ? "bg-[#F0EEFF] font-medium text-[#4238CA]" : "text-[#475467] hover:bg-[#F9FAFB]"}`}><span>全部文稿</span><span className="text-xs">{presentations.length}</span></button>
              <button type="button" onClick={() => setActiveFolder("root")} className={`mt-1 flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm ${activeFolder === "root" ? "bg-[#F0EEFF] font-medium text-[#4238CA]" : "text-[#475467] hover:bg-[#F9FAFB]"}`}><span>未分类</span><span className="text-xs">{presentations.filter((item) => !item.folder_id).length}</span></button>
              <div className="my-2 border-t border-[#EAECF0]" />
              {folderRows.map((folder) => (
                <div key={folder.id} className="group flex items-center gap-1" style={{ paddingLeft: `${folder.depth * 14}px` }}>
                  <button type="button" onClick={() => setActiveFolder(folder.id)} className={`flex min-w-0 flex-1 items-center justify-between rounded-lg px-2 py-2 text-left text-sm ${activeFolder === folder.id ? "bg-[#F0EEFF] font-medium text-[#4238CA]" : "text-[#475467] hover:bg-[#F9FAFB]"}`}>
                    <span className="flex min-w-0 items-center gap-2"><Folder className="h-4 w-4 shrink-0" /><span className="truncate">{folder.name}</span></span><span className="ml-2 text-xs">{folderCounts.get(folder.id) || 0}</span>
                  </button>
                  {canEdit && <button type="button" onClick={() => openEditFolder(folder)} className="rounded p-1 text-[#98A2B3] opacity-0 hover:bg-[#F2F4F7] hover:text-[#475467] group-hover:opacity-100 focus:opacity-100" aria-label={`编辑${folder.name}`}><Pencil className="h-3.5 w-3.5" /></button>}
                </div>
              ))}
              {!folderRows.length && <p className="px-3 py-5 text-center text-xs text-[#98A2B3]">暂无自定义文件夹</p>}
            </aside>

            <section className="min-w-0">
              <div className="rounded-2xl border border-[#E4E7EC] bg-white p-4">
                <div className="grid gap-3 md:grid-cols-[minmax(220px,1fr)_150px_150px]">
                  <label className="relative"><span className="sr-only">搜索文稿</span><Search className="absolute left-3 top-3 h-4 w-4 text-[#98A2B3]" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索文稿名称" className="h-10 w-full rounded-lg border border-[#D0D5DD] pl-9 pr-3 text-sm outline-none focus:border-[#8B7DFF]" /></label>
                  <select value={status} onChange={(event) => setStatus(event.target.value)} className="h-10 rounded-lg border border-[#D0D5DD] bg-white px-3 text-sm text-[#344054]"><option value="all">全部状态</option>{Object.entries(statusLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
                  <select value={creationMode} onChange={(event) => setCreationMode(event.target.value)} className="h-10 rounded-lg border border-[#D0D5DD] bg-white px-3 text-sm text-[#344054]"><option value="all">全部创建方式</option>{Object.entries(creationModeLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
                </div>
                {canEdit && selected.length > 0 && (
                  <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl bg-[#F8F7FF] px-4 py-3">
                    <span className="text-sm font-medium text-[#4238CA]">已选择 {selected.length} 项</span>
                    <select value={moveTarget} onChange={(event) => setMoveTarget(event.target.value)} className="h-9 min-w-[180px] rounded-lg border border-[#C7C2FF] bg-white px-3 text-sm"><option value="root">未分类（根目录）</option>{folderRows.map((folder) => <option key={folder.id} value={folder.id}>{"　".repeat(folder.depth)}{folder.name}</option>)}</select>
                    <button type="button" disabled={pending === "move"} onClick={movePresentations} className="inline-flex h-9 items-center rounded-lg bg-[#635BFF] px-3 text-sm font-medium text-white disabled:opacity-50">{pending === "move" && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}批量移动</button>
                    <button type="button" onClick={() => setSelected([])} className="text-sm text-[#667085]">取消选择</button>
                  </div>
                )}
              </div>

              <div className="mt-4 overflow-hidden rounded-2xl border border-[#E4E7EC] bg-white">
                <div className="flex items-center border-b border-[#EAECF0] bg-[#F9FAFB] px-4 py-3 text-xs font-medium text-[#667085]">
                  {canEdit && <input type="checkbox" checked={allVisibleSelected} onChange={() => setSelected(allVisibleSelected ? selected.filter((id) => !visiblePresentations.some((item) => item.id === id)) : Array.from(new Set([...selected, ...visiblePresentations.map((item) => item.id)])))} className="mr-3 h-4 w-4 rounded border-[#D0D5DD]" aria-label="选择全部可见文稿" />}
                  <span>共 {visiblePresentations.length} 份文稿</span>
                </div>
                {visiblePresentations.map((item) => (
                  <article key={item.id} className="flex flex-col gap-4 border-b border-[#EAECF0] px-4 py-4 last:border-b-0 sm:flex-row sm:items-center">
                    {canEdit && <input type="checkbox" checked={selected.includes(item.id)} onChange={() => setSelected((current) => current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id])} className="h-4 w-4 shrink-0 rounded border-[#D0D5DD]" aria-label={`选择${item.title || "未命名文稿"}`} />}
                    <div className="flex min-w-0 flex-1 items-start gap-3"><div className="rounded-lg bg-[#F0EEFF] p-2 text-[#635BFF]"><FileText className="h-5 w-5" /></div><div className="min-w-0"><h2 className="truncate text-sm font-semibold text-[#101828]">{item.title || "未命名文稿"}</h2><div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[#667085]"><span>{creationModeLabel[item.creation_mode]}</span><span>{folderNames.get(item.folder_id || "") || "未分类"}</span><span>{new Date(item.updated_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}</span></div></div></div>
                    <div className="flex items-center gap-2 pl-11 sm:pl-0"><span className="rounded-full bg-[#F2F4F7] px-2.5 py-1 text-xs text-[#475467]">{statusLabel[item.status]}</span><Link href={`/workspace/presentations/${item.id}?workspace_id=${encodeURIComponent(workspaceId)}`} className="inline-flex h-8 items-center gap-1 rounded-lg border border-[#D0D5DD] px-2.5 text-xs text-[#344054] hover:bg-[#F9FAFB]">治理详情<ChevronRight className="h-3.5 w-3.5" /></Link>{item.can_open && <Link href={`/presentation?id=${encodeURIComponent(item.presentation_id)}&type=standard`} className="inline-flex h-8 items-center gap-1 rounded-lg bg-[#101828] px-2.5 text-xs text-white">打开<ExternalLink className="h-3.5 w-3.5" /></Link>}</div>
                  </article>
                ))}
                {!visiblePresentations.length && <div className="py-16 text-center"><FileText className="mx-auto h-8 w-8 text-[#D0D5DD]" /><p className="mt-3 text-sm font-medium text-[#475467]">没有符合条件的文稿</p><p className="mt-1 text-xs text-[#98A2B3]">可调整文件夹或筛选条件后重试</p></div>}
              </div>
            </section>
          </div>
        )}
      </div>

      {folderDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/40 p-4">
          <div role="dialog" aria-modal="true" aria-labelledby="folder-dialog-title" className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl">
            <div className="flex items-center justify-between"><h2 id="folder-dialog-title" className="text-lg font-semibold text-[#101828]">{folderDialog === "create" ? "新建文件夹" : "编辑文件夹"}</h2><button type="button" onClick={() => setFolderDialog(null)} className="rounded-lg p-1 text-[#667085] hover:bg-[#F2F4F7]"><X className="h-5 w-5" /></button></div>
            <form onSubmit={saveFolder} className="mt-5 space-y-4"><label className="block text-sm font-medium text-[#344054]">文件夹名称<input autoFocus value={folderName} onChange={(event) => setFolderName(event.target.value)} maxLength={200} className="mt-1.5 h-10 w-full rounded-lg border border-[#D0D5DD] px-3 text-sm outline-none focus:border-[#8B7DFF]" /></label><label className="block text-sm font-medium text-[#344054]">上级文件夹<select value={folderParent} onChange={(event) => setFolderParent(event.target.value)} className="mt-1.5 h-10 w-full rounded-lg border border-[#D0D5DD] bg-white px-3 text-sm"><option value="root">根目录</option>{folderRows.filter((folder) => !unavailableParentIds.has(folder.id)).map((folder) => <option key={folder.id} value={folder.id}>{"　".repeat(folder.depth)}{folder.name}</option>)}</select></label><div className="flex items-center justify-between border-t border-[#EAECF0] pt-4"><div>{folderDialog !== "create" && <button type="button" onClick={() => { setArchiveTarget(folderDialog); setFolderDialog(null); }} className="inline-flex items-center gap-1.5 text-sm text-[#B42318]"><Archive className="h-4 w-4" />归档文件夹</button>}</div><div className="flex gap-2"><button type="button" onClick={() => setFolderDialog(null)} className="h-9 rounded-lg border border-[#D0D5DD] px-3 text-sm">取消</button><button type="submit" disabled={!folderName.trim() || pending === "folder"} className="inline-flex h-9 items-center rounded-lg bg-[#635BFF] px-4 text-sm font-medium text-white disabled:opacity-50">{pending === "folder" && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}保存</button></div></div></form>
          </div>
        </div>
      )}

      {archiveTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/40 p-4">
          <div role="alertdialog" aria-modal="true" aria-labelledby="archive-title" className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl"><div className="flex items-start gap-3"><div className="rounded-full bg-[#FEF3F2] p-2 text-[#B42318]"><AlertTriangle className="h-5 w-5" /></div><div><h2 id="archive-title" className="font-semibold text-[#101828]">归档“{archiveTarget.name}”</h2><p className="mt-1 text-sm text-[#667085]">只能归档空文件夹。归档后不会再显示在文稿中心。</p></div></div><div className="mt-5 flex justify-end gap-2"><button type="button" onClick={() => setArchiveTarget(null)} className="h-9 rounded-lg border border-[#D0D5DD] px-3 text-sm">取消</button><button type="button" disabled={pending === "archive"} onClick={archiveFolder} className="inline-flex h-9 items-center rounded-lg bg-[#D92D20] px-4 text-sm font-medium text-white disabled:opacity-50">{pending === "archive" && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}确认归档</button></div></div>
        </div>
      )}
    </main>
  );
}
