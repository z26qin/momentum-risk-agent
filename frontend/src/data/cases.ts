import type { CaseBundle, CaseData } from "./types";

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
