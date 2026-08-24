import { expect, type APIRequestContext, type Page } from "@playwright/test";

export interface WorkspaceFixture {
  id: string;
  name: string;
  current_user_role: string;
  workspace_type: "personal" | "team" | "department";
}

interface AdminUserFixture {
  id: string;
  username: string;
}

export interface ViewerCredentials {
  username: string;
  password: string;
}

export async function getPrimaryWorkspace(request: APIRequestContext): Promise<WorkspaceFixture> {
  const response = await request.get("/api/v1/enterprise/workspaces");
  expect(response.ok(), `Workspace fixture lookup failed with HTTP ${response.status()}`).toBeTruthy();
  const workspaces = await response.json() as WorkspaceFixture[];
  expect(workspaces.length, "Authenticated release-gate account needs an enterprise workspace").toBeGreaterThan(0);
  const managed = workspaces.find((item) =>
    item.name === "E2E 发布门禁工作空间"
    && item.workspace_type === "team"
    && ["owner", "admin"].includes(item.current_user_role)
  ) || workspaces.find((item) =>
    item.workspace_type !== "personal"
    && ["owner", "admin"].includes(item.current_user_role)
    && item.name.startsWith("E2E ")
  );
  if (managed) return managed;

  const createResponse = await request.post("/api/v1/enterprise/workspaces", {
    data: {
      name: "E2E 发布门禁工作空间",
      workspace_type: "team",
      confidentiality: "L2",
    },
  });
  if (!createResponse.ok()) {
    throw new Error(`Managed workspace fixture creation failed with HTTP ${createResponse.status()}: ${await createResponse.text()}`);
  }
  return await createResponse.json() as WorkspaceFixture;
}

export async function ensureViewerAccount(
  request: APIRequestContext,
  workspaceId: string
): Promise<ViewerCredentials> {
  const username = "e2e_release_viewer";
  const password = `E2E!${crypto.randomUUID()}Aa1`;
  const usersResponse = await request.get("/api/v1/admin/users");
  expect(usersResponse.ok(), `Admin user fixture lookup failed with HTTP ${usersResponse.status()}`).toBeTruthy();
  const users = await usersResponse.json() as AdminUserFixture[];
  let viewer = users.find((item) => item.username === username);

  if (!viewer) {
    const createResponse = await request.post("/api/v1/admin/users", {
      data: { username, password },
    });
    expect(createResponse.ok(), `Viewer fixture creation failed with HTTP ${createResponse.status()}`).toBeTruthy();
    viewer = await createResponse.json() as AdminUserFixture;
  } else {
    const resetResponse = await request.put(`/api/v1/admin/users/${encodeURIComponent(viewer.id)}/password`, {
      data: { password },
    });
    expect(resetResponse.ok(), `Viewer fixture password reset failed with HTTP ${resetResponse.status()}`).toBeTruthy();
  }

  const membershipResponse = await request.post(
    `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/members`,
    { data: { username, role: "viewer" } }
  );
  expect(membershipResponse.ok(), `Viewer membership fixture failed with HTTP ${membershipResponse.status()}: ${await membershipResponse.text()}`).toBeTruthy();
  return { username, password };
}

export async function ensureBidProject(request: APIRequestContext, workspaceId: string): Promise<string> {
  const listResponse = await request.get(`/api/v1/enterprise/bid/projects?workspace_id=${encodeURIComponent(workspaceId)}`);
  expect(listResponse.ok()).toBeTruthy();
  const projects = await listResponse.json() as Array<{ id: string; bid_code: string }>;
  const existing = projects.find((item) => item.bid_code === "E2E-RELEASE-GATE") || projects[0];
  if (existing) return existing.id;

  const dueDate = new Date();
  dueDate.setDate(dueDate.getDate() + 21);
  let lastFailure = "";
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const fixtureCode = `E2E-${Date.now().toString(36).toUpperCase()}-${crypto.randomUUID().slice(0, 6).toUpperCase()}`;
    const createResponse = await request.post("/api/v1/enterprise/bid/projects", {
      data: {
        workspace_id: workspaceId,
        bid_code: fixtureCode,
        name: "企业 PPT 发布门禁竞标项目",
        sponsor_name: "E2E Fixture",
        due_date: dueDate.toISOString().slice(0, 10),
        confidentiality: "L3",
      },
    });
    if (createResponse.ok()) return (await createResponse.json() as { id: string }).id;
    lastFailure = `HTTP ${createResponse.status()}: ${await createResponse.text()}`;
  }
  throw new Error(`Bid fixture creation failed after retries: ${lastFailure}`);
}

export async function expectBasicAccessibility(page: Page, root = "body") {
  const violations = await page.locator(root).evaluate((container) => {
    const issues: string[] = [];
    container.querySelectorAll("button").forEach((button, index) => {
      const name = button.getAttribute("aria-label") || button.getAttribute("title") || button.textContent?.trim();
      if (!name) issues.push(`button[${index}] has no accessible name`);
    });
    container.querySelectorAll("img").forEach((image, index) => {
      if (!image.hasAttribute("alt")) issues.push(`img[${index}] has no alt attribute`);
    });
    container.querySelectorAll("input, select, textarea").forEach((control, index) => {
      const id = control.getAttribute("id");
      const labelled = control.hasAttribute("aria-label")
        || control.hasAttribute("aria-labelledby")
        || Boolean(id && container.querySelector(`label[for="${CSS.escape(id)}"]`))
        || Boolean(control.closest("label"))
        || control.hasAttribute("placeholder");
      if (!labelled) issues.push(`form control[${index}] has no accessible label`);
    });
    return issues;
  });
  expect(violations, violations.join("\n")).toEqual([]);
}

export async function expectPerformanceBudget(page: Page) {
  await page.waitForLoadState("load");
  await page.waitForFunction(() => performance.getEntriesByName("first-contentful-paint").length > 0);
  const metrics = await page.evaluate(() => {
    const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming;
    const firstContentfulPaint = performance.getEntriesByName("first-contentful-paint")[0];
    return {
      responseStart: navigation.responseStart,
      domContentLoaded: navigation.domContentLoadedEventEnd,
      load: navigation.loadEventEnd,
      firstContentfulPaint: firstContentfulPaint.startTime,
    };
  });
  const budget = {
    responseStart: Number(process.env.PLAYWRIGHT_PERF_TTFB_MS || 2500),
    domContentLoaded: Number(process.env.PLAYWRIGHT_PERF_DCL_MS || 5000),
    load: Number(process.env.PLAYWRIGHT_PERF_LOAD_MS || 8000),
    firstContentfulPaint: Number(process.env.PLAYWRIGHT_PERF_FCP_MS || 4000),
  };
  for (const metric of Object.keys(budget) as Array<keyof typeof budget>) {
    expect(metrics[metric], `${metric} ${metrics[metric].toFixed(0)}ms exceeded ${budget[metric]}ms`).toBeLessThanOrEqual(budget[metric]);
  }
}
