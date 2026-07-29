import type {
  AnalyticsRun,
  AnalyticsComparison,
  DemoResponse,
  ImportDetail,
  ImportSummary,
  Overview,
  PipelineRun
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    }
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  overview: () => request<Overview>("/api/v1/learning/overview"),
  imports: () => request<ImportSummary[]>("/api/v1/learning/imports"),
  importDetail: (id: string) =>
    request<ImportDetail>(`/api/v1/learning/imports/${id}`),
  runDemo: () =>
    request<DemoResponse>("/api/v1/learning/demos/import", { method: "POST" }),
  pipelines: () => request<PipelineRun[]>("/api/v1/learning/pipelines"),
  analytics: () => request<AnalyticsRun[]>("/api/v1/learning/analytics"),
  compareAnalytics: () =>
    request<AnalyticsComparison>("/api/v1/learning/analytics/compare", {
      method: "POST",
      body: JSON.stringify({ row_count: 5000, repeats: 5, seed: 20260729 })
    }),
  runReconciliation: (engine: "pandas" | "polars") =>
    request<AnalyticsRun>("/api/v1/analytics/reconciliations", {
      method: "POST",
      body: JSON.stringify({ engine, row_count: 1000, seed: 20260729 })
    }),
  runRisk: () =>
    request<AnalyticsRun>("/api/v1/analytics/stockout-risks", {
      method: "POST",
      body: JSON.stringify({ row_count: 1000, seed: 20260729 })
    })
};
