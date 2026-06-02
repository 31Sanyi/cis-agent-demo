import type { Report, WorkflowSummary } from "../api/types";

export function workflowContractSource(summary?: WorkflowSummary): "core" | "legacy" | "none" {
  if (summary?.core) return "core";
  if (summary) return "legacy";
  return "none";
}

export function reportContractSource(report?: Report): "core" | "legacy" | "none" {
  if (report?.json_report.core) return "core";
  if (report?.json_report) return "legacy";
  return "none";
}
