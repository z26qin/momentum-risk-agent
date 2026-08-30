import { execFile } from "node:child_process";
import type { ServerResponse } from "node:http";
import path from "node:path";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, type Connect, type Plugin } from "vite";

const execFileAsync = promisify(execFile);
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const supportedDates = new Set(["2020-03-24", "2024-01-05", "2026-05-29"]);

function sendJson(res: ServerResponse, status: number, payload: unknown) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(JSON.stringify(payload));
}

function attachConsoleApi(server: { middlewares: Connect.Server }) {
  server.middlewares.use((req, res, next) => {
    const url = req.url?.split("?")[0] ?? "";
    const match = url.match(/^\/api\/run\/([^/]+)$/);
    if (!match || req.method !== "POST") {
      next();
      return;
    }
    let asOfDate = "";
    try {
      asOfDate = decodeURIComponent(match[1]);
    } catch {
      sendJson(res, 400, { error: "invalid encoded date" });
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(asOfDate) || !supportedDates.has(asOfDate)) {
      sendJson(res, 400, { error: `unsupported console date: ${asOfDate}` });
      return;
    }
    const python = path.join(repoRoot, ".venv", "bin", "python");
    execFileAsync(python, ["scripts/run_console_case.py", asOfDate], {
      cwd: repoRoot,
      timeout: 45_000,
      maxBuffer: 8 * 1024 * 1024,
    })
      .then(({ stdout }) => {
        res.statusCode = 200;
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.end(stdout);
      })
      .catch((reason: unknown) => {
        const error = reason as { stderr?: string; message?: string };
        sendJson(res, 500, { error: error.stderr?.trim() || error.message || "re-run failed" });
      });
  });
}

function consoleApi(): Plugin {
  return {
    name: "local-console-api",
    configureServer: attachConsoleApi,
    configurePreviewServer: attachConsoleApi,
  };
}

export default defineConfig({
  plugins: [tailwindcss(), react(), consoleApi()],
});
