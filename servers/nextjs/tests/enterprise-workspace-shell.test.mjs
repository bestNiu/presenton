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
  assert.match(shell, /文档与知识/);
  assert.match(shell, /模板中心/);
  assert.match(shell, /资产中心/);
  assert.match(shell, /交付中心/);
  assert.match(shell, /current_user_role/);
});

test("enterprise resource pages consume the shared workspace context", async () => {
  const pages = await Promise.all(
    [
      "page.tsx",
      "documents/page.tsx",
      "templates/page.tsx",
      "assets/page.tsx",
      "deliveries/page.tsx",
      "scenes/[sceneType]/page.tsx",
    ].map(readWorkspaceFile)
  );

  for (const source of pages) {
    assert.match(source, /useEnterpriseWorkspace/);
  }
});
