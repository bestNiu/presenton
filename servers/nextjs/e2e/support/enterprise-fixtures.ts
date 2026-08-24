import { expect, type APIRequestContext, type Page } from "@playwright/test";

export interface WorkspaceFixture {
  id: string;
  current_user_role: string;
  workspace_type: "personal" | "team" | "department";
}

export async function getPrimaryWorkspace(request: APIRequestContext): Promise<WorkspaceFixture> {
  const response = await request.get("/api/v1/enterprise/workspaces");
  expect(response.ok(), `Workspace fixture lookup failed with HTTP ${response.status()}`).toBeTruthy();
  const workspaces = await response.json() as WorkspaceFixture[];
  expect(workspaces.length, "Authenticated release-gate account needs an enterprise workspace").toBeGreaterThan(0);
  return workspaces.find((item) => item.workspace_type !== "personal" && ["owner", "admin"].includes(item.current_user_role))
    || workspaces.find((item) => item.workspace_type !== "personal")
    || workspaces[0];
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
