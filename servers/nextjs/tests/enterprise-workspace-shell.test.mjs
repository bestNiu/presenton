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
  assert.match(shell, /评审任务/);
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
  assert.match(page, /只看我创建的/);
  assert.match(page, /最近更新/);
  assert.match(page, /新建文稿/);
  assert.match(page, /确认恢复/);
  assert.match(page, /批量归档/);
  assert.match(page, /复制到工作空间/);
  assert.match(page, /可独立编辑的文稿和页面副本/);
  assert.match(page, /批量恢复/);
  assert.match(page, /归档保留/);
  assert.match(page, /预检过期文稿/);
  assert.match(page, /永久删除/);
  assert.match(page, /\/review\?workspace_id=/);
  assert.match(page, /role="alertdialog"/);
  assert.doesNotMatch(page, /window\.confirm/);
  assert.match(enterpriseApi, /createFolder/);
  assert.match(enterpriseApi, /updateFolder/);
  assert.match(enterpriseApi, /archiveFolder/);
  assert.match(enterpriseApi, /movePresentations/);
  assert.match(enterpriseApi, /getPresentationCatalog/);
  assert.match(enterpriseApi, /archivePresentation/);
  assert.match(enterpriseApi, /restorePresentation/);
  assert.match(enterpriseApi, /bulkUpdatePresentationLifecycle/);
  assert.match(enterpriseApi, /copyPresentation/);
  assert.match(enterpriseApi, /purgePresentation/);
  assert.match(enterpriseApi, /runPresentationArchiveLifecycle/);
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
  assert.match(settings, /归档文稿保留天数/);
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

test("enterprise resource centers expose governed detail views", async () => {
  const [documents, templates, assets, drawer, enterpriseApi] = await Promise.all([
    readWorkspaceFile("documents/page.tsx"),
    readWorkspaceFile("templates/page.tsx"),
    readWorkspaceFile("assets/page.tsx"),
    readWorkspaceFile("components/ResourceDetailDrawer.tsx"),
    readFile(new URL("../app/(presentation-generator)/services/api/enterprise.ts", import.meta.url), "utf8"),
  ]);

  assert.match(drawer, /当前治理状态/);
  assert.match(drawer, /版本时间线/);
  assert.match(documents, /解析内容预览/);
  assert.match(documents, /下载原文件/);
  assert.match(documents, /getDocumentDetail/);
  assert.match(templates, /企业模板详情/);
  assert.match(templates, /模板预览/);
  assert.match(assets, /企业资产详情/);
  assert.match(assets, /累计复用/);
  assert.match(assets, /授权有效期/);
  assert.match(enterpriseApi, /documents\/\$\{encodeURIComponent\(documentId\)\}/);
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

test("review task center supports cross-presentation triage and bulk actions", async () => {
  const [page, reviewPage, editor, enterpriseApi] = await Promise.all([
    readWorkspaceFile("reviews/page.tsx"),
    readWorkspaceFile("presentations/[entryId]/review/page.tsx"),
    readFile(new URL("../app/(presentation-generator)/presentation/components/PresentationPage.tsx", import.meta.url), "utf8"),
    readFile(
      new URL(
        "../app/(presentation-generator)/services/api/enterprise.ts",
        import.meta.url
      ),
      "utf8"
    ),
  ]);

  assert.match(page, /评审任务中心/);
  assert.match(page, /列表/);
  assert.match(page, /看板/);
  assert.match(page, /只看我的/);
  assert.match(page, /仅看逾期/);
  assert.match(page, /批量解决/);
  assert.match(page, /批量重开/);
  assert.match(page, /批量调度/);
  assert.match(page, /应用负责人\/截止时间/);
  assert.match(page, /bulkUpdatePresentationReviewTasks/);
  assert.match(page, /thread_id=/);
  assert.match(reviewPage, /focusedThreadId/);
  assert.match(reviewPage, /进入画布整改/);
  assert.match(editor, /initialSlideApplied/);
  assert.match(page, /role="dialog"/);
  assert.match(page, /presentation_entry_id/);
  assert.match(enterpriseApi, /getPresentationReviewInbox/);
  assert.match(enterpriseApi, /transitionPresentationComment/);
  assert.match(enterpriseApi, /review-inbox\/bulk-update/);
});

test("presentation review exposes a selectable frozen version timeline", async () => {
  const page = await readWorkspaceFile("presentations/[entryId]/review/page.tsx");

  assert.match(page, /版本时间线与差异/);
  assert.match(page, /当前冻结版/);
  assert.match(page, /比较所选版本/);
  assert.match(page, /comparePresentationSnapshots/);
  assert.match(page, /getPresentationSnapshotEvidence/);
});

test("delivery incidents use an auditable decision form", async () => {
  const page = await readWorkspaceFile("deliveries/page.tsx");

  assert.match(page, /完整性异常处置/);
  assert.match(page, /处置依据/);
  assert.match(page, /确认提交处置/);
  assert.match(page, /role="dialog"/);
  assert.doesNotMatch(page, /window\.prompt/);
});

test("general presentation creation is a four-step enterprise wizard", async () => {
  const [catalog, wizard, generation, upload, enterpriseApi] = await Promise.all([
    readWorkspaceFile("presentations/page.tsx"),
    readWorkspaceFile("components/PresentationCreationWizard.tsx"),
    readWorkspaceFile("presentations/[entryId]/generation/page.tsx"),
    readFile(new URL("../app/(presentation-generator)/upload/components/UploadPage.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/(presentation-generator)/services/api/enterprise.ts", import.meta.url), "utf8"),
  ]);

  assert.match(catalog, /PresentationCreationWizard/);
  assert.match(wizard, /选择创建方式/);
  assert.match(wizard, /配置内容/);
  assert.match(wizard, /选择设计/);
  assert.match(wizard, /确认并创建/);
  assert.match(wizard, /主题生成/);
  assert.match(wizard, /企业资料/);
  assert.match(wizard, /企业模板/);
  assert.match(wizard, /空白文稿/);
  assert.match(wizard, /导入文件/);
  assert.match(wizard, /getDocuments/);
  assert.match(wizard, /getPublishedTemplates/);
  assert.match(wizard, /品牌与生成约束/);
  assert.match(wizard, /enterprise\.generationTasks/);
  assert.match(wizard, /createKnowledgePresentation/);
  assert.match(generation, /getKnowledgeOutline/);
  assert.match(generation, /自动刷新/);
  assert.match(generation, /进入大纲确认/);
  assert.match(enterpriseApi, /folder_id: input\.folderId/);
  assert.match(enterpriseApi, /instructions: input\.instructions/);
  assert.match(upload, /requestedSlides/);
  assert.match(upload, /requestedLanguage/);
  assert.match(upload, /requestedTone/);
  assert.match(upload, /requestedInstructions/);
});

test("bid project exposes six-stage progress and a derived task panel", async () => {
  const page = await readWorkspaceFile("scenes/bid/projects/[projectId]/page.tsx");

  assert.match(page, /竞标项目六阶段导航/);
  assert.match(page, /资料与理解/);
  assert.match(page, /策略确认/);
  assert.match(page, /专业协作/);
  assert.match(page, /Gate 门禁/);
  assert.match(page, /组装版本/);
  assert.match(page, /交付归档/);
  assert.match(page, /项目任务面板/);
  assert.match(page, /项目阶段完成度/);
  assert.match(page, /最终截止/);
  assert.match(page, /登记问题/);
  assert.match(page, /处置记录/);
  assert.match(page, /项目动态/);
  assert.match(page, /createBidGateIssue/);
  assert.match(page, /resolveBidGateIssue/);
});

test("playwright release gate covers workspace creation and review flows", async () => {
  const [config, spec, fixtures, packageJson] = await Promise.all([
    readFile(new URL("../playwright.config.ts", import.meta.url), "utf8"),
    readFile(new URL("../e2e/enterprise-workspace.spec.ts", import.meta.url), "utf8"),
    readFile(new URL("../e2e/support/enterprise-fixtures.ts", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  assert.match(config, /Desktop Chrome/);
  assert.match(spec, /enterprise PPT workspace release gate/);
  assert.match(spec, /评审任务中心/);
  assert.match(spec, /竞标项目六阶段导航/);
  assert.match(spec, /surfaces API failure and recovers/);
  assert.match(spec, /basic accessibility gate/);
  assert.match(spec, /Page emitted unhandled runtime errors/);
  assert.match(fixtures, /ensureBidProject/);
  assert.match(fixtures, /expectBasicAccessibility/);
  assert.match(packageJson, /test:e2e:enterprise/);
  assert.match(packageJson, /test:release-gate/);
});
