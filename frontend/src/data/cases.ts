import type { CaseBundle, CaseData } from "./types";

export const SUPPORTED_DATES = ["2020-03-24", "2024-01-05", "2026-05-29"] as const;

function isCaseBundle(value: unknown): value is CaseBundle {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<CaseBundle>;
  return (
    candidate.schema_version === "investigation-console-bundle-v1" &&
    Array.isArray(candidate.cases) &&
    candidate.cases.length === 3
  );
}

export async function loadCases(): Promise<CaseData[]> {
  const response = await fetch("/cases.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`case export unavailable (${response.status})`);
  const payload: unknown = await response.json();
  if (!isCaseBundle(payload)) throw new Error("case export has an unexpected contract");
  return payload.cases;
}

export async function rerunCase(asOfDate: string): Promise<CaseData> {
  if (!(SUPPORTED_DATES as readonly string[]).includes(asOfDate)) {
    throw new Error(`unsupported console date: ${asOfDate}`);
  }
  const response = await fetch(`/api/run/${encodeURIComponent(asOfDate)}`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const message = payload && typeof payload === "object" && "error" in payload
      ? String(payload.error)
      : `re-run failed (${response.status})`;
    throw new Error(message);
  }
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object" || !("date" in payload)) {
    throw new Error("re-run returned an unexpected contract");
  }
  return payload as CaseData;
}
