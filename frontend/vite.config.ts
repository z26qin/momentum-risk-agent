import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, type Connect, type Plugin } from "vite";

const execFileAsync = promisify(execFile);
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function attachConsoleApi(server: { middlewares: Connect.Server }) {
  server.middlewares.use((req, res, next) => {
    const url = req.url?.split("?")[0] ?? "";
    const match = url.match(/^\/api\/run\/([^/]+)$/);
    if (!match || req.method !== "POST") {
      next();
      return;
    }
    const caseId = decodeURIComponent(match[1]);
    const venvPython = path.join(repoRoot, ".venv", "bin", "python");
    execFileAsync(venvPython, ["scripts/run_console_case.py", caseId], {
      cwd: repoRoot,
      timeout: 45_000,
      maxBuffer: 8 * 1024 * 1024,
    })
      .then(({ stdout }) => {
        res.statusCode = 200;
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.end(stdout);
      })
      .catch((error: unknown) => {
        const err = error as { stderr?: string; message?: string };
        res.statusCode = 500;
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.end(JSON.stringify({ error: err.stderr || err.message || "re-run failed" }));
      });
  });
}

function consoleApi(): Plugin {
  return {
    name: "console-api",
    configureServer: attachConsoleApi,
    configurePreviewServer: attachConsoleApi,
  };
}

export default defineConfig({
  plugins: [tailwindcss(), react(), consoleApi()],
});
