import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { transform } from "esbuild";

const source = await readFile(
  new URL("../utils/apiErrorMessages.ts", import.meta.url),
  "utf8"
);
const { code } = await transform(source, {
  loader: "ts",
  format: "esm",
  target: "es2022",
});
const moduleUrl = `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`;
const { extractApiErrorMessage, sanitizeApiErrorMessage } = await import(moduleUrl);

test("generic server messages do not leak into the workspace UI", () => {
  assert.equal(
    extractApiErrorMessage(
      { detail: "Internal server error. Please try again later." },
      "工作空间加载失败，请稍后重试",
      500
    ),
    "工作空间加载失败，请稍后重试"
  );
  assert.equal(
    sanitizeApiErrorMessage(
      "502 Bad Gateway",
      "专业场景加载失败，其他工作台功能仍可继续使用",
      502
    ),
    "专业场景加载失败，其他工作台功能仍可继续使用"
  );
});

test("actionable business errors remain visible", () => {
  assert.equal(
    extractApiErrorMessage(
      { detail: "Workspace name is required" },
      "团队工作空间创建失败，请稍后重试",
      422
    ),
    "Workspace name is required"
  );
});
