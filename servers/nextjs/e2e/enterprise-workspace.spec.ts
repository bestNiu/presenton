import { expect, test, type Page } from "@playwright/test";
import {
  ensureBidProject,
  ensureViewerAccount,
  expectBasicAccessibility,
  expectPerformanceBudget,
  getPrimaryWorkspace,
} from "./support/enterprise-fixtures";

const username = process.env.PLAYWRIGHT_USERNAME;
const password = process.env.PLAYWRIGHT_PASSWORD;
const runtimeErrors = new WeakMap<Page, string[]>();

async function signIn(page: Page) {
  test.skip(!username || !password, "Set PLAYWRIGHT_USERNAME and PLAYWRIGHT_PASSWORD to run authenticated workspace flows");
  const response = await page.request.post("/api/v1/auth/login", {
    data: { username, password },
  });
  expect(response.ok(), `Login failed with HTTP ${response.status()}`).toBeTruthy();
}

test.describe("enterprise PPT workspace release gate", () => {
  test.beforeEach(async ({ page }) => {
    const errors: string[] = [];
    runtimeErrors.set(page, errors);
    page.on("pageerror", (error) => errors.push(error.message));
    await signIn(page);
  });

  test.afterEach(async ({ page }) => {
    expect(runtimeErrors.get(page) || [], "Page emitted unhandled runtime errors").toEqual([]);
  });

  test("opens the general workspace and completes creation-wizard review", async ({ page }) => {
    await page.addInitScript(() => {
      const telemetryEvents: unknown[] = [];
      Object.defineProperty(window, "__enterpriseE2EEvents", { value: telemetryEvents });
      window.addEventListener("enterprise:telemetry", (event) => {
        telemetryEvents.push((event as CustomEvent).detail);
      });
    });
    await page.goto("/workspace/presentations");
    await expect(page.getByRole("heading", { name: "文稿中心" })).toBeVisible();
    await expectPerformanceBudget(page);
    const configurationToast = page.getByRole("button", { name: "Got it!" });
    await configurationToast.waitFor({ state: "visible", timeout: 2_000 }).catch(() => undefined);
    if (await configurationToast.isVisible()) await configurationToast.click();

    await page.getByRole("button", { name: "新建文稿" }).click();
    await expect(page.getByRole("heading", { name: "选择创建方式" })).toBeVisible();
    const wizardPanel = page.locator('[role="dialog"] > div').first();
    await expect(wizardPanel).toHaveScreenshot("creation-wizard-mode.png", {
      animations: "disabled",
      maxDiffPixelRatio: 0.01,
    });
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
    await expectBasicAccessibility(page, "[role=dialog]");
    await expect(wizardPanel).toHaveScreenshot("creation-wizard-review.png", {
      animations: "disabled",
      maxDiffPixelRatio: 0.01,
    });
    await page.getByRole("button", { name: "确认并创建" }).click();
    await expect(page).toHaveURL(/\/upload\?/);
    const telemetry = await page.evaluate(() =>
      (window as unknown as { __enterpriseE2EEvents: Array<{ event: string }> }).__enterpriseE2EEvents.map((item) => item.event)
    );
    expect(telemetry).toContain("Enterprise Creation Wizard Opened");
    expect(telemetry).toContain("Enterprise Presentation Creation Requested");
    expect(telemetry).toContain("Enterprise Presentation Creation Accepted");
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
    const workspace = await getPrimaryWorkspace(page.request);
    const projectId = await ensureBidProject(page.request, workspace.id);
    await page.goto(`/workspace/scenes/bid/projects/${projectId}`);
    await expect(page.getByRole("navigation", { name: "竞标项目六阶段导航" })).toBeVisible();
    await expect(page.getByText("项目任务面板")).toBeVisible();
    await expect(page.getByText("项目阶段完成度")).toBeVisible();
  });

  test("surfaces API failure and recovers after retry navigation", async ({ page }) => {
    await page.route("**/api/v1/enterprise/workspaces/*/presentations/search?*", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Internal server error. Please try again later." }),
      });
    });
    await page.goto("/workspace/presentations");
    await expect(page.getByText(/Internal server error|文稿目录加载失败/)).toBeVisible();

    await page.unroute("**/api/v1/enterprise/workspaces/*/presentations/search?*");
    await page.reload();
    await expect(page.getByRole("heading", { name: "文稿中心" })).toBeVisible();
  });

  test("workspace resource centers meet the basic accessibility gate", async ({ page }) => {
    const centers = [
      ["/workspace/documents", "企业文档与知识中心"],
      ["/workspace/templates", "模板发布治理"],
      ["/workspace/assets", "企业资产中心"],
    ] as const;
    for (const [path, heading] of centers) {
      await page.goto(path);
      await expect(page.getByRole("heading", { name: heading })).toBeVisible();
      await expectBasicAccessibility(page);
    }
  });

  test("viewer role remains read-only in workspace governance", async ({ page }) => {
    const workspace = await getPrimaryWorkspace(page.request);
    const viewer = await ensureViewerAccount(page.request, workspace.id);
    const response = await page.request.post("/api/v1/auth/login", {
      data: viewer,
    });
    expect(response.ok()).toBeTruthy();
    await page.goto(`/workspace/settings?workspace_id=${encodeURIComponent(workspace.id)}`);
    await expect(page.getByText("只读").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "添加成员" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "保存治理策略" })).toHaveCount(0);
    const forbiddenMutation = await page.request.put(
      `/api/v1/enterprise/workspaces/${encodeURIComponent(workspace.id)}`,
      { data: { name: "viewer must not update", confidentiality: "L2" } }
    );
    expect(
      [403, 404],
      "Viewer writes must be forbidden or hidden without revealing the resource",
    ).toContain(forbiddenMutation.status());
  });
});
