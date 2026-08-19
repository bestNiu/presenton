import { expect, test, type Page } from "@playwright/test";

const username = process.env.PLAYWRIGHT_USERNAME;
const password = process.env.PLAYWRIGHT_PASSWORD;

async function signIn(page: Page) {
  test.skip(!username || !password, "Set PLAYWRIGHT_USERNAME and PLAYWRIGHT_PASSWORD to run authenticated workspace flows");
  const response = await page.request.post("/api/v1/auth/login", {
    data: { username, password },
  });
  expect(response.ok(), `Login failed with HTTP ${response.status()}`).toBeTruthy();
}

test.describe("enterprise PPT workspace release gate", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page);
  });

  test("opens the general workspace and completes creation-wizard review", async ({ page }) => {
    await page.goto("/workspace/presentations");
    await expect(page.getByRole("heading", { name: "文稿中心" })).toBeVisible();

    await page.getByRole("button", { name: "新建文稿" }).click();
    await expect(page.getByRole("heading", { name: "选择创建方式" })).toBeVisible();
    await page.getByRole("button", { name: /主题生成/ }).click();
    await page.getByRole("button", { name: "下一步" }).click();

    await page.getByLabel("文稿主题").fill("企业年度经营复盘");
    await page.getByLabel("目标受众").fill("公司管理层");
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByRole("button", { name: /管理层汇报/ }).click();
    await page.getByRole("button", { name: "下一步" }).click();

    await expect(page.getByText("创建摘要")).toBeVisible();
    await expect(page.getByText("企业年度经营复盘")).toBeVisible();
    await expect(page.getByRole("button", { name: "确认并创建" })).toBeEnabled();
  });

  test("opens cross-presentation review tasks and switches to board view", async ({ page }) => {
    await page.goto("/workspace/reviews");
    await expect(page.getByRole("heading", { name: "评审任务中心" })).toBeVisible();
    await page.getByRole("button", { name: "看板" }).click();
    await expect(page.getByText("已逾期", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("阻断整改", { exact: true })).toBeVisible();
    await expect(page.getByText("一般待办", { exact: true })).toBeVisible();
  });

  test("shows bid six-stage navigation when a project fixture is provided", async ({ page }) => {
    const workspaceResponse = await page.request.get("/api/v1/enterprise/workspaces");
    expect(workspaceResponse.ok()).toBeTruthy();
    const workspaces = await workspaceResponse.json() as Array<{ id: string }>;
    test.skip(!workspaces[0], "No enterprise workspace is available");
    const projectResponse = await page.request.get(`/api/v1/enterprise/bid/projects?workspace_id=${encodeURIComponent(workspaces[0].id)}`);
    expect(projectResponse.ok()).toBeTruthy();
    const projects = await projectResponse.json() as Array<{ id: string }>;
    test.skip(!projects[0], "No seeded bid project is available");
    const projectId = projects[0].id;
    await page.goto(`/workspace/scenes/bid/projects/${projectId}`);
    await expect(page.getByRole("navigation", { name: "竞标项目六阶段导航" })).toBeVisible();
    await expect(page.getByText("项目任务面板")).toBeVisible();
    await expect(page.getByText("项目阶段完成度")).toBeVisible();
  });
});
