/**
 * Frozen cases exported from `run_orchestrated_investigation()`.
 *
 * Runtime source: /cases.json (written by scripts/export_frontend_cases.py).
 * Bundled fallback: ./generated/cases.json (same payload, so the console
 * still renders if the public file is missing).
 *
 * Regenerate both with:
 *   uv run python scripts/export_frontend_cases.py
 */

import generated from "./generated/cases.json";
import type { CaseData } from "./types";

export const ALL_CASES = generated as CaseData[];

function isCaseList(value: unknown): value is CaseData[] {
  return Array.isArray(value) && value.length > 0 && typeof value[0]?.id === "string";
}

export async function loadCases(): Promise<CaseData[]> {
  try {
    const response = await fetch("/cases.json", { cache: "no-store" });
    if (!response.ok) return ALL_CASES;
    const payload: unknown = await response.json();
    return isCaseList(payload) ? payload : ALL_CASES;
  } catch {
    return ALL_CASES;
  }
}
