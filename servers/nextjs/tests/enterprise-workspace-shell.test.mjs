import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const workspaceRoot = new URL(
  "../app/(presentation-generator)/(dashboard)/workspace/",
  import.meta.url
);

const readWorkspaceFile = (path) =>
  readFile(new URL(path, workspaceRoot), "utf8");

test("workspace routes are wrapped by the shared enterprise shell", async () => {
  const [layout, shell] = await Promise.all([
    readWorkspaceFile("layout.tsx"),
    readWorkspaceFile("components/EnterpriseWorkspaceShell.tsx"),
  ]);

  assert.match(layout, /<EnterpriseWorkspaceShell>/);
  assert.match(shell, /enterprise\.activeWorkspaceId/);
  assert.match(shell, /工作台总览/);
  assert.match(shell, /文稿中心/);
  assert.match(shell, /文档与知识/);
  assert.match(shell, /模板中心/);
  assert.match(shell, /资产中心/);
  assert.match(shell, /交付中心/);
  assert.match(shell, /工作区设置/);
  assert.match(shell, /current_user_role/);
});

test("presentation center supports folder organization and bulk movement", async () => {
  const [page, enterpriseApi] = await Promise.all([
    readWorkspaceFile("presentations/page.tsx"),
    readFile(
      new URL(
        "../app/(presentation-generator)/services/api/enterprise.ts",
        import.meta.url
      ),
      "utf8"
    ),
  ]);

  assert.match(page, /集中检索、分类和维护/);
  assert.match(page, /新建文件夹/);
  assert.match(page, /批量移动/);
  assert.match(page, /role="alertdialog"/);
  assert.doesNotMatch(page, /window\.confirm/);
  assert.match(enterpriseApi, /createFolder/);
  assert.match(enterpriseApi, /updateFolder/);
  assert.match(enterpriseApi, /archiveFolder/);
  assert.match(enterpriseApi, /movePresentations/);
});

test("workspace settings exposes business-friendly governance and member flows", async () => {
  const [settings, enterpriseApi] = await Promise.all([
    readWorkspaceFile("settings/page.tsx"),
    readFile(
      new URL(
        "../app/(presentation-generator)/services/api/enterprise.ts",
        import.meta.url
      ),
      "utf8"
    ),
  ]);

  assert.match(settings, /基本信息/);
  assert.match(settings, /治理策略/);
  assert.match(settings, /成员与角色/);
  assert.match(settings, /最近审计记录/);
  assert.match(settings, /role="dialog"/);
  assert.doesNotMatch(settings, /window\.confirm/);
  assert.match(enterpriseApi, /inviteWorkspaceMember/);
  assert.match(enterpriseApi, /updateWorkspaceMember/);
  assert.match(enterpriseApi, /removeWorkspaceMember/);
});

test("enterprise resource pages consume the shared workspace context", async () => {
  const pages = await Promise.all(
    [
      "page.tsx",
      "documents/page.tsx",
      "templates/page.tsx",
      "assets/page.tsx",
      "deliveries/page.tsx",
      "presentations/page.tsx",
      "scenes/[sceneType]/page.tsx",
    ].map(readWorkspaceFile)
  );

  for (const source of pages) {
    assert.match(source, /useEnterpriseWorkspace/);
  }
});

test("workspace home prioritizes work overview and removes management clutter", async () => {
  const [page, overview] = await Promise.all([
    readWorkspaceFile("page.tsx"),
    readWorkspaceFile("components/WorkspaceHomeOverview.tsx"),
  ]);

  assert.match(page, /工作台总览/);
  assert.match(page, /通用 PPT 创建/);
  assert.match(page, /整改任务箱/);
  assert.match(page, /最近文稿/);
  assert.doesNotMatch(page, />我的空间</);
  assert.doesNotMatch(page, />已发布模板</);
  assert.match(overview, /今日工作概览/);
  assert.match(overview, /待处理任务/);
  assert.match(overview, /阻断与风险/);
  assert.match(overview, /快捷入口/);
});
