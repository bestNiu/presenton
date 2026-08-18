"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  ChevronRight,
  Copy,
  ExternalLink,
  FileText,
  Folder,
  FolderPlus,
  Loader2,
  Pencil,
  Plus,
  RotateCcw,
  Search,
  X,
} from "lucide-react";

import {
  EnterpriseApi,
  type FolderResponse,
  type PresentationCatalogItemResponse,
  type PresentationCreationMode,
  type PresentationEntryResponse,
} from "@/app/(presentation-generator)/services/api/enterprise";
import { PresentationGenerationApi } from "@/app/(presentation-generator)/services/api/presentation-generation";
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
  const router = useRouter();
  const {
    activeWorkspace: workspace,
    activeWorkspaceId: workspaceId,
    workspaces,
  } = useEnterpriseWorkspace();
  const [folders, setFolders] = useState<FolderResponse[]>([]);
  const [presentations, setPresentations] = useState<PresentationCatalogItemResponse[]>([]);
  const [activeFolder, setActiveFolder] = useState<"all" | "root" | string>("all");
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [creationMode, setCreationMode] = useState("all");
  const [mineOnly, setMineOnly] = useState(false);
  const [sortBy, setSortBy] = useState<
    "updated_desc" | "updated_asc" | "title_asc" | "title_desc" | "created_desc"
  >("updated_desc");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [moveTarget, setMoveTarget] = useState("root");
  const [folderDialog, setFolderDialog] = useState<FolderResponse | "create" | null>(null);
  const [folderName, setFolderName] = useState("");
  const [folderParent, setFolderParent] = useState("root");
  const [archiveTarget, setArchiveTarget] = useState<FolderResponse | null>(null);
  const [presentationLifecycleTarget, setPresentationLifecycleTarget] =
    useState<PresentationCatalogItemResponse | null>(null);
  const [copyTarget, setCopyTarget] =
    useState<PresentationCatalogItemResponse | null>(null);
  const [copyWorkspaceId, setCopyWorkspaceId] = useState("");
  const [copyFolderId, setCopyFolderId] = useState("root");
  const [copyTitle, setCopyTitle] = useState("");
  const [copyFolders, setCopyFolders] = useState<FolderResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const canEdit = ["owner", "admin", "editor"].includes(
    workspace?.current_user_role || "viewer"
  );
  const editableWorkspaces = useMemo(
    () =>
      workspaces.filter((item) =>
        ["owner", "admin", "editor"].includes(item.current_user_role)
      ),
    [workspaces]
  );

  useEffect(() => {
    if (!copyTarget || !copyWorkspaceId) {
      setCopyFolders([]);
      return;
    }
    let active = true;
    EnterpriseApi.getFolders(copyWorkspaceId)
      .then((rows) => {
        if (active) setCopyFolders(rows);
      })
      .catch((cause) => {
        if (active) {
          setCopyFolders([]);
          setError(cause instanceof Error ? cause.message : "目标文件夹加载失败");
        }
      });
    return () => {
      active = false;
    };
  }, [copyTarget, copyWorkspaceId]);

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
      const [folderRows, catalog] = await Promise.all([
        EnterpriseApi.getFolders(workspaceId),
        EnterpriseApi.getPresentationCatalog(workspaceId, {
          query: search || undefined,
          folder_id:
            activeFolder !== "all" && activeFolder !== "root"
              ? activeFolder
              : undefined,
          unfiled_only: activeFolder === "root" || undefined,
          presentation_status:
            status === "all"
              ? undefined
              : (status as PresentationEntryResponse["status"]),
          creation_mode:
            creationMode === "all"
              ? undefined
              : (creationMode as PresentationCreationMode),
          mine_only: mineOnly || undefined,
          sort_by: sortBy,
          page,
          page_size: 20,
        }),
      ]);
      setFolders(folderRows);
      setPresentations(catalog.items);
      setTotal(catalog.total);
      setPages(catalog.pages);
      setSelected([]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "文稿中心加载失败");
    } finally {
      setLoading(false);
    }
  }, [activeFolder, creationMode, mineOnly, page, search, sortBy, status, workspaceId]);

  useEffect(() => {
    void load();
  }, [load]);

  const folderRows = useMemo(() => flattenFolders(folders), [folders]);
  const copyFolderRows = useMemo(
    () => flattenFolders(copyFolders),
    [copyFolders]
  );
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
  const selectFolder = (folderId: "all" | "root" | string) => {
    setActiveFolder(folderId);
    setPage(1);
  };

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

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    setPage(1);
    setSearch(searchDraft.trim());
  };

  const createHref = (entry: "topic" | "document" | "template") => {
    const params = new URLSearchParams({ entry, workspace_id: workspaceId });
    if (entry === "template") params.set("template", "executive");
    return `/upload?${params.toString()}`;
  };

  const createBlankPresentation = () => {
    if (!workspaceId || !canEdit) return;
    void runAction(
      "create-blank",
      async () => {
        const presentation =
          await PresentationGenerationApi.createBlankPresentation({
            workspace_id: workspaceId,
            scene_type: "general",
          });
        router.push(
          `/presentation?id=${encodeURIComponent(presentation.id)}&type=standard`
        );
      },
      "空白文稿已创建"
    );
  };

  const changePresentationLifecycle = () => {
    if (!workspaceId || !presentationLifecycleTarget) return;
    const target = presentationLifecycleTarget;
    const restoring = target.status === "archived";
    void runAction(
      "presentation-lifecycle",
      async () => {
        if (restoring) {
          await EnterpriseApi.restorePresentation(workspaceId, target.id);
        } else {
          await EnterpriseApi.archivePresentation(workspaceId, target.id);
        }
        setPresentationLifecycleTarget(null);
        await load();
      },
      restoring ? "文稿已恢复为草稿" : "文稿已归档"
    );
  };

  const bulkArchivePresentations = () => {
    if (!workspaceId || !selected.length) return;
    void runAction(
      "bulk-archive",
      async () => {
        await EnterpriseApi.bulkUpdatePresentationLifecycle(
          workspaceId,
          selected,
          "archive"
        );
        await load();
      },
      `已归档 ${selected.length} 份文稿`
    );
  };

  const openCopyDialog = (item: PresentationCatalogItemResponse) => {
    const preferredWorkspace =
      editableWorkspaces.find((candidate) => candidate.id !== workspaceId) ||
      editableWorkspaces[0];
    if (!preferredWorkspace) return;
    setCopyTarget(item);
    setCopyWorkspaceId(preferredWorkspace.id);
    setCopyFolderId("root");
    setCopyTitle(`${item.title || "未命名文稿"}（副本）`);
  };

  const copyPresentation = (event: FormEvent) => {
    event.preventDefault();
    if (!workspaceId || !copyTarget || !copyWorkspaceId) return;
    const targetWorkspace = editableWorkspaces.find(
      (candidate) => candidate.id === copyWorkspaceId
    );
    void runAction(
      "copy-presentation",
      async () => {
        await EnterpriseApi.copyPresentation(workspaceId, copyTarget.id, {
          target_workspace_id: copyWorkspaceId,
          target_folder_id: copyFolderId === "root" ? null : copyFolderId,
          title: copyTitle.trim() || undefined,
        });
        setCopyTarget(null);
        if (copyWorkspaceId === workspaceId) await load();
      },
      `文稿已复制到${targetWorkspace ? `“${targetWorkspace.name}”` : "目标工作空间"}`
    );
  };

  const movablePresentations = presentations.filter(
    (item) => item.status !== "archived"
  );
  const selectedItems = presentations.filter((item) =>
    selected.includes(item.id)
  );
  const canBulkArchive =
    selectedItems.length === selected.length &&
    selectedItems.every((item) => item.status === "draft");
  const allVisibleSelected =
    movablePresentations.length > 0 &&
    movablePresentations.every((item) => selected.includes(item.id));

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
            <div className="flex items-center gap-2">
              <button type="button" onClick={openCreateFolder} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-[#D0D5DD] bg-white px-4 text-sm font-medium text-[#344054] hover:bg-[#F9FAFB]">
                <FolderPlus className="h-4 w-4" />新建文件夹
              </button>
              <details className="group relative">
                <summary className="flex h-10 cursor-pointer list-none items-center gap-2 rounded-lg bg-[#635BFF] px-4 text-sm font-medium text-white hover:bg-[#5147E5]">
                  <Plus className="h-4 w-4" />新建文稿
                </summary>
                <div className="absolute right-0 z-20 mt-2 w-44 rounded-xl border border-[#E4E7EC] bg-white p-1.5 shadow-lg">
                  <Link href={createHref("topic")} className="block rounded-lg px-3 py-2 text-sm text-[#344054] hover:bg-[#F5F3FF]">从主题生成</Link>
                  <Link href={createHref("document")} className="block rounded-lg px-3 py-2 text-sm text-[#344054] hover:bg-[#F5F3FF]">从文档生成</Link>
                  <Link href={createHref("template")} className="block rounded-lg px-3 py-2 text-sm text-[#344054] hover:bg-[#F5F3FF]">从模板创建</Link>
                  <button type="button" onClick={createBlankPresentation} disabled={pending === "create-blank"} className="flex w-full items-center rounded-lg px-3 py-2 text-left text-sm text-[#344054] hover:bg-[#F5F3FF] disabled:opacity-50">
                    {pending === "create-blank" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}空白文稿
                  </button>
                </div>
              </details>
            </div>
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
              <button type="button" onClick={() => selectFolder("all")} className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm ${activeFolder === "all" ? "bg-[#F0EEFF] font-medium text-[#4238CA]" : "text-[#475467] hover:bg-[#F9FAFB]"}`}><span>全部文稿</span>{activeFolder === "all" && <span className="text-xs">{total}</span>}</button>
              <button type="button" onClick={() => selectFolder("root")} className={`mt-1 flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm ${activeFolder === "root" ? "bg-[#F0EEFF] font-medium text-[#4238CA]" : "text-[#475467] hover:bg-[#F9FAFB]"}`}><span>未分类</span>{activeFolder === "root" && <span className="text-xs">{total}</span>}</button>
              <div className="my-2 border-t border-[#EAECF0]" />
              {folderRows.map((folder) => (
                <div key={folder.id} className="group flex items-center gap-1" style={{ paddingLeft: `${folder.depth * 14}px` }}>
                  <button type="button" onClick={() => selectFolder(folder.id)} className={`flex min-w-0 flex-1 items-center justify-between rounded-lg px-2 py-2 text-left text-sm ${activeFolder === folder.id ? "bg-[#F0EEFF] font-medium text-[#4238CA]" : "text-[#475467] hover:bg-[#F9FAFB]"}`}>
                    <span className="flex min-w-0 items-center gap-2"><Folder className="h-4 w-4 shrink-0" /><span className="truncate">{folder.name}</span></span>{activeFolder === folder.id && <span className="ml-2 text-xs">{total}</span>}
                  </button>
                  {canEdit && <button type="button" onClick={() => openEditFolder(folder)} className="rounded p-1 text-[#98A2B3] opacity-0 hover:bg-[#F2F4F7] hover:text-[#475467] group-hover:opacity-100 focus:opacity-100" aria-label={`编辑${folder.name}`}><Pencil className="h-3.5 w-3.5" /></button>}
                </div>
              ))}
              {!folderRows.length && <p className="px-3 py-5 text-center text-xs text-[#98A2B3]">暂无自定义文件夹</p>}
            </aside>

            <section className="min-w-0">
              <div className="rounded-2xl border border-[#E4E7EC] bg-white p-4">
                <form onSubmit={submitSearch} className="grid gap-3 md:grid-cols-[minmax(220px,1fr)_auto]">
                  <label className="relative"><span className="sr-only">搜索文稿</span><Search className="absolute left-3 top-3 h-4 w-4 text-[#98A2B3]" /><input value={searchDraft} onChange={(event) => setSearchDraft(event.target.value)} placeholder="搜索文稿名称" className="h-10 w-full rounded-lg border border-[#D0D5DD] pl-9 pr-3 text-sm outline-none focus:border-[#8B7DFF]" /></label>
                  <button type="submit" className="h-10 rounded-lg bg-[#101828] px-4 text-sm font-medium text-white">搜索</button>
                </form>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }} className="h-10 rounded-lg border border-[#D0D5DD] bg-white px-3 text-sm text-[#344054]"><option value="all">全部状态</option>{Object.entries(statusLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
                  <select value={creationMode} onChange={(event) => { setCreationMode(event.target.value); setPage(1); }} className="h-10 rounded-lg border border-[#D0D5DD] bg-white px-3 text-sm text-[#344054]"><option value="all">全部创建方式</option>{Object.entries(creationModeLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
                  <select value={sortBy} onChange={(event) => { setSortBy(event.target.value as typeof sortBy); setPage(1); }} className="h-10 rounded-lg border border-[#D0D5DD] bg-white px-3 text-sm text-[#344054]"><option value="updated_desc">最近更新</option><option value="updated_asc">最早更新</option><option value="created_desc">最近创建</option><option value="title_asc">名称 A-Z</option><option value="title_desc">名称 Z-A</option></select>
                  <label className="flex h-10 items-center gap-2 rounded-lg border border-[#D0D5DD] px-3 text-sm text-[#344054]"><input type="checkbox" checked={mineOnly} onChange={(event) => { setMineOnly(event.target.checked); setPage(1); }} className="h-4 w-4 rounded border-[#D0D5DD]" />只看我创建的</label>
                </div>
                {canEdit && selected.length > 0 && (
                  <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl bg-[#F8F7FF] px-4 py-3">
                    <span className="text-sm font-medium text-[#4238CA]">已选择 {selected.length} 项</span>
                    <select value={moveTarget} onChange={(event) => setMoveTarget(event.target.value)} className="h-9 min-w-[180px] rounded-lg border border-[#C7C2FF] bg-white px-3 text-sm"><option value="root">未分类（根目录）</option>{folderRows.map((folder) => <option key={folder.id} value={folder.id}>{"　".repeat(folder.depth)}{folder.name}</option>)}</select>
                    <button type="button" disabled={pending === "move"} onClick={movePresentations} className="inline-flex h-9 items-center rounded-lg bg-[#635BFF] px-3 text-sm font-medium text-white disabled:opacity-50">{pending === "move" && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}批量移动</button>
                    <button type="button" disabled={!canBulkArchive || pending === "bulk-archive"} onClick={bulkArchivePresentations} title={canBulkArchive ? "归档所选草稿" : "批量归档仅支持草稿文稿"} className="inline-flex h-9 items-center rounded-lg border border-[#FDA29B] bg-white px-3 text-sm font-medium text-[#B42318] disabled:opacity-40">{pending === "bulk-archive" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Archive className="mr-2 h-4 w-4" />}批量归档</button>
                    <button type="button" onClick={() => setSelected([])} className="text-sm text-[#667085]">取消选择</button>
                  </div>
                )}
              </div>

              <div className="mt-4 overflow-hidden rounded-2xl border border-[#E4E7EC] bg-white">
                <div className="flex items-center border-b border-[#EAECF0] bg-[#F9FAFB] px-4 py-3 text-xs font-medium text-[#667085]">
                  {canEdit && movablePresentations.length > 0 && <input type="checkbox" checked={allVisibleSelected} onChange={() => setSelected(allVisibleSelected ? selected.filter((id) => !movablePresentations.some((item) => item.id === id)) : Array.from(new Set([...selected, ...movablePresentations.map((item) => item.id)])))} className="mr-3 h-4 w-4 rounded border-[#D0D5DD]" aria-label="选择全部可见文稿" />}
                  <span>共 {total} 份文稿</span>
                </div>
                {presentations.map((item) => (
                  <article key={item.id} className="flex flex-col gap-4 border-b border-[#EAECF0] px-4 py-4 last:border-b-0 sm:flex-row sm:items-center">
                    {canEdit && item.status !== "archived" && <input type="checkbox" checked={selected.includes(item.id)} onChange={() => setSelected((current) => current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id])} className="h-4 w-4 shrink-0 rounded border-[#D0D5DD]" aria-label={`选择${item.title || "未命名文稿"}`} />}
                    <div className="flex min-w-0 flex-1 items-start gap-3"><div className="rounded-lg bg-[#F0EEFF] p-2 text-[#635BFF]"><FileText className="h-5 w-5" /></div><div className="min-w-0"><h2 className="truncate text-sm font-semibold text-[#101828]">{item.title || "未命名文稿"}</h2><div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[#667085]"><span>{creationModeLabel[item.creation_mode]}</span><span>{folderNames.get(item.folder_id || "") || "未分类"}</span><span>创建人：{item.creator_username || "未知"}</span><span>{new Date(item.updated_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}</span></div></div></div>
                    <div className="flex flex-wrap items-center gap-2 pl-11 sm:justify-end sm:pl-0"><span className="rounded-full bg-[#F2F4F7] px-2.5 py-1 text-xs text-[#475467]">{statusLabel[item.status]}</span>{item.status !== "archived" && <Link href={`/workspace/presentations/${item.id}/review?workspace_id=${encodeURIComponent(workspaceId)}`} className="inline-flex h-8 items-center gap-1 rounded-lg border border-[#D0D5DD] px-2.5 text-xs text-[#344054] hover:bg-[#F9FAFB]">治理详情<ChevronRight className="h-3.5 w-3.5" /></Link>}{item.can_open && item.status !== "archived" && <Link href={`/presentation?id=${encodeURIComponent(item.presentation_id)}&type=standard&workspace_id=${encodeURIComponent(workspaceId)}&entry_id=${encodeURIComponent(item.id)}`} className="inline-flex h-8 items-center gap-1 rounded-lg bg-[#101828] px-2.5 text-xs text-white">打开<ExternalLink className="h-3.5 w-3.5" /></Link>}{item.status !== "archived" && editableWorkspaces.length > 0 && <button type="button" onClick={() => openCopyDialog(item)} className="inline-flex h-8 items-center gap-1 rounded-lg border border-[#B9B2FF] px-2.5 text-xs text-[#5146E5]"><Copy className="h-3.5 w-3.5" />复制</button>}{canEdit && (item.status === "draft" || item.status === "archived") && <button type="button" onClick={() => setPresentationLifecycleTarget(item)} className={`inline-flex h-8 items-center gap-1 rounded-lg border px-2.5 text-xs ${item.status === "archived" ? "border-[#B9B2FF] text-[#5146E5]" : "border-[#FDA29B] text-[#B42318]"}`}>{item.status === "archived" ? <RotateCcw className="h-3.5 w-3.5" /> : <Archive className="h-3.5 w-3.5" />}{item.status === "archived" ? "恢复" : "归档"}</button>}</div>
                  </article>
                ))}
                {!presentations.length && <div className="py-16 text-center"><FileText className="mx-auto h-8 w-8 text-[#D0D5DD]" /><p className="mt-3 text-sm font-medium text-[#475467]">没有符合条件的文稿</p><p className="mt-1 text-xs text-[#98A2B3]">可调整文件夹或筛选条件后重试</p></div>}
              </div>
              {pages > 1 && <div className="mt-4 flex items-center justify-between text-sm text-[#667085]"><span>第 {page} / {pages} 页</span><div className="flex gap-2"><button type="button" disabled={page <= 1 || loading} onClick={() => setPage((current) => Math.max(1, current - 1))} className="h-9 rounded-lg border border-[#D0D5DD] bg-white px-3 disabled:opacity-40">上一页</button><button type="button" disabled={page >= pages || loading} onClick={() => setPage((current) => Math.min(pages, current + 1))} className="h-9 rounded-lg border border-[#D0D5DD] bg-white px-3 disabled:opacity-40">下一页</button></div></div>}
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

      {copyTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/40 p-4">
          <div role="dialog" aria-modal="true" aria-labelledby="copy-presentation-title" className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl">
            <div className="flex items-center justify-between">
              <div><h2 id="copy-presentation-title" className="font-semibold text-[#101828]">复制到工作空间</h2><p className="mt-1 text-sm text-[#667085]">将创建可独立编辑的文稿和页面副本。</p></div>
              <button type="button" onClick={() => setCopyTarget(null)} className="rounded-lg p-1 text-[#667085] hover:bg-[#F2F4F7]"><X className="h-5 w-5" /></button>
            </div>
            <form onSubmit={copyPresentation} className="mt-5 space-y-4">
              <label className="block text-sm font-medium text-[#344054]">副本名称<input value={copyTitle} onChange={(event) => setCopyTitle(event.target.value)} maxLength={500} className="mt-1.5 h-10 w-full rounded-lg border border-[#D0D5DD] px-3 text-sm outline-none focus:border-[#8B7DFF]" /></label>
              <label className="block text-sm font-medium text-[#344054]">目标工作空间<select value={copyWorkspaceId} onChange={(event) => { setCopyWorkspaceId(event.target.value); setCopyFolderId("root"); }} className="mt-1.5 h-10 w-full rounded-lg border border-[#D0D5DD] bg-white px-3 text-sm">{editableWorkspaces.map((item) => <option key={item.id} value={item.id}>{item.name}{item.id === workspaceId ? "（当前）" : ""}</option>)}</select></label>
              <label className="block text-sm font-medium text-[#344054]">目标文件夹<select value={copyFolderId} onChange={(event) => setCopyFolderId(event.target.value)} className="mt-1.5 h-10 w-full rounded-lg border border-[#D0D5DD] bg-white px-3 text-sm"><option value="root">未分类（根目录）</option>{copyFolderRows.map((folder) => <option key={folder.id} value={folder.id}>{"　".repeat(folder.depth)}{folder.name}</option>)}</select></label>
              <div className="flex justify-end gap-2 border-t border-[#EAECF0] pt-4"><button type="button" onClick={() => setCopyTarget(null)} className="h-9 rounded-lg border border-[#D0D5DD] px-3 text-sm">取消</button><button type="submit" disabled={!copyWorkspaceId || pending === "copy-presentation"} className="inline-flex h-9 items-center rounded-lg bg-[#635BFF] px-4 text-sm font-medium text-white disabled:opacity-50">{pending === "copy-presentation" && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}创建副本</button></div>
            </form>
          </div>
        </div>
      )}

      {presentationLifecycleTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/40 p-4">
          <div role="alertdialog" aria-modal="true" aria-labelledby="presentation-lifecycle-title" className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl">
            <div className="flex items-start gap-3">
              <div className={`rounded-full p-2 ${presentationLifecycleTarget.status === "archived" ? "bg-[#F0EEFF] text-[#635BFF]" : "bg-[#FEF3F2] text-[#B42318]"}`}>
                {presentationLifecycleTarget.status === "archived" ? <RotateCcw className="h-5 w-5" /> : <Archive className="h-5 w-5" />}
              </div>
              <div>
                <h2 id="presentation-lifecycle-title" className="font-semibold text-[#101828]">{presentationLifecycleTarget.status === "archived" ? "恢复" : "归档"}“{presentationLifecycleTarget.title || "未命名文稿"}”</h2>
                <p className="mt-1 text-sm text-[#667085]">{presentationLifecycleTarget.status === "archived" ? "恢复后文稿将回到草稿状态，并出现在未分类目录。" : "归档后文稿将从日常列表移入已归档视图，之后仍可恢复。"}</p>
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => setPresentationLifecycleTarget(null)} className="h-9 rounded-lg border border-[#D0D5DD] px-3 text-sm">取消</button>
              <button type="button" disabled={pending === "presentation-lifecycle"} onClick={changePresentationLifecycle} className={`inline-flex h-9 items-center rounded-lg px-4 text-sm font-medium text-white disabled:opacity-50 ${presentationLifecycleTarget.status === "archived" ? "bg-[#635BFF]" : "bg-[#D92D20]"}`}>{pending === "presentation-lifecycle" && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{presentationLifecycleTarget.status === "archived" ? "确认恢复" : "确认归档"}</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
