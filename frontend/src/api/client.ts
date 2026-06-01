import type { CollectorStatus, Dag, Evidence, LlmStatus, QaResult, Report, SearchTestResult, Survey, SurveyAnalysis, SurveyQuestionCreate, SurveyPlannerContext, SurveyRevisionResponse, SurveyTopicGenerateRequest, SurveyUpdateRequest, SurveyUploadResponse, Task, TaskRun, TraceRecord } from "./types";
import { apiRecorder } from "./recorder";

const baseUrl = "";

type RequestOptions = RequestInit & {
  label: string;
};

function parseQuery(url: string): Record<string, string> {
  const queryIndex = url.indexOf("?");
  if (queryIndex < 0) return {};
  return Object.fromEntries(new URLSearchParams(url.slice(queryIndex + 1)).entries());
}

async function request<T>(url: string, options: RequestOptions): Promise<T> {
  const { label, ...fetchOptions } = options;
  const requestBody = typeof fetchOptions.body === "string"
    ? (() => {
        try {
          return JSON.parse(fetchOptions.body);
        } catch {
          return fetchOptions.body;
        }
      })()
    : fetchOptions.body;
  const complete = apiRecorder.start({
    label,
    url,
    method: fetchOptions.method ?? "GET",
    query: parseQuery(url),
    requestBody,
  });
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${url}`, {
      headers: { "Content-Type": "application/json" },
      ...fetchOptions
    });
  } catch (error) {
    complete({
      errorMessage: error instanceof Error ? error.message : String(error),
    });
    throw error;
  }
  const responseText = await response.text();
  const responseBody = responseText
    ? (() => {
        try {
          return JSON.parse(responseText);
        } catch {
          return responseText;
        }
      })()
    : undefined;
  if (!response.ok) {
    complete({
      responseStatus: response.status,
      responseOk: response.ok,
      responseBody,
      errorMessage: typeof responseBody === "string" ? responseBody : JSON.stringify(responseBody),
    });
    throw new Error(typeof responseBody === "string" ? responseBody : JSON.stringify(responseBody));
  }
  complete({
    responseStatus: response.status,
    responseOk: response.ok,
    responseBody,
  });
  return responseBody as T;
}

async function uploadRequest<T>(url: string, formData: FormData): Promise<T> {
  const response = await fetch(`${baseUrl}${url}`, {
    method: "POST",
    body: formData
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

async function textRequest(url: string): Promise<string> {
  const response = await fetch(`${baseUrl}${url}`);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.text();
}

export const api = {
  createTask: (payload: { product_name: string; competitors: string[]; region: string; industry: string }) =>
    request<Task>("/api/tasks", { label: "createTask", method: "POST", body: JSON.stringify(payload) }),
  listTasks: () => request<Task[]>("/api/tasks", { label: "listTasks", method: "GET" }),
  runTask: (taskId: string, demoMode = "normal", autoRework = false, writerMode = "mock", collectorMode = "mock", analystMode = "evidence", workflowEngine = "custom") =>
    request(`/api/tasks/${taskId}/run?demo_mode=${encodeURIComponent(demoMode)}&auto_rework=${autoRework}&writer_mode=${encodeURIComponent(writerMode)}&collector_mode=${encodeURIComponent(collectorMode)}&analyst_mode=${encodeURIComponent(analystMode)}&workflow_engine=${encodeURIComponent(workflowEngine)}`, { label: "runTask", method: "POST" }),
  dag: (taskId: string) => request<Dag>(`/api/tasks/${taskId}/dag`, { label: "dag", method: "GET" }),
  evidence: (taskId: string) => request<Evidence[]>(`/api/tasks/${taskId}/evidence`, { label: "evidence", method: "GET" }),
  qa: (taskId: string) => request<QaResult>(`/api/tasks/${taskId}/qa`, { label: "qa", method: "GET" }),
  report: (taskId: string) => request<Report>(`/api/tasks/${taskId}/report`, { label: "report", method: "GET" }),
  traces: (taskId: string) => request<TraceRecord[]>(`/api/tasks/${taskId}/traces`, { label: "traces", method: "GET" }),
  runs: (taskId: string) => request<TaskRun[]>(`/api/tasks/${taskId}/runs`, { label: "runs", method: "GET" }),
  latestRun: (taskId: string) => request<TaskRun>(`/api/tasks/${taskId}/runs/latest`, { label: "latestRun", method: "GET" }),
  runEvidence: (taskId: string, runId: string) => request<Evidence[]>(`/api/tasks/${taskId}/runs/${runId}/evidence`, { label: "runEvidence", method: "GET" }),
  runQa: (taskId: string, runId: string) => request<QaResult>(`/api/tasks/${taskId}/runs/${runId}/qa`, { label: "runQa", method: "GET" }),
  runReport: (taskId: string, runId: string) => request<Report>(`/api/tasks/${taskId}/runs/${runId}/report`, { label: "runReport", method: "GET" }),
  runTraces: (taskId: string, runId: string) => request<TraceRecord[]>(`/api/tasks/${taskId}/runs/${runId}/traces`, { label: "runTraces", method: "GET" }),
  runSurvey: (taskId: string, runId: string) => request<Survey>(`/api/tasks/${taskId}/runs/${runId}/survey`, { label: "runSurvey", method: "GET" }),
  surveyPlannerContext: (taskId: string) => request<SurveyPlannerContext>(`/api/tasks/${taskId}/survey/context`, { label: "surveyPlannerContext", method: "GET" }),
  generateTaskSurvey: (taskId: string, forceGenerate = false) =>
    request<Survey>(`/api/tasks/${taskId}/survey/generate?force_generate=${forceGenerate}`, { label: "generateTaskSurvey", method: "POST" }),
  refineTaskSurvey: (taskId: string, payload: { survey_id: string; instruction: string }) =>
    request<SurveyRevisionResponse>(`/api/tasks/${taskId}/survey/refine`, { label: "refineTaskSurvey", method: "POST", body: JSON.stringify(payload) }),
  exportTaskSurveyCsv: (taskId: string) => textRequest(`/api/tasks/${taskId}/survey/export-csv`),
  surveyTaskAnalysis: (taskId: string) => request<SurveyAnalysis | { status: string }>(`/api/tasks/${taskId}/survey/analysis`, { label: "surveyTaskAnalysis", method: "GET" }),
  generateSurvey: (taskId: string, runId: string, payload: Record<string, unknown>) =>
    request<Survey>(`/api/tasks/${taskId}/runs/${runId}/survey/generate`, { label: "generateSurvey", method: "POST", body: JSON.stringify(payload) }),
  createPhoneDemoSurvey: (taskId: string, runId: string) =>
    request<SurveyUploadResponse>(`/api/tasks/${taskId}/runs/${runId}/survey/demo-phone`, { label: "createPhoneDemoSurvey", method: "POST" }),
  generateSurveyFromTopic: (payload: SurveyTopicGenerateRequest) =>
    request<Survey>("/api/surveys/generate-from-topic", { label: "generateSurveyFromTopic", method: "POST", body: JSON.stringify(payload) }),
  updateSurvey: (surveyId: string, payload: SurveyUpdateRequest) =>
    request<Survey>(`/api/surveys/${surveyId}`, { label: "updateSurvey", method: "PATCH", body: JSON.stringify(payload) }),
  addSurveyQuestion: (surveyId: string, question?: SurveyQuestionCreate) =>
    request<Survey>(`/api/surveys/${surveyId}/questions`, { label: "addSurveyQuestion", method: "POST", body: JSON.stringify(question ? { question } : {}) }),
  deleteSurveyQuestion: (surveyId: string, questionId: string) =>
    request<Survey>(`/api/surveys/${surveyId}/questions/${questionId}`, { label: "deleteSurveyQuestion", method: "DELETE" }),
  reorderSurveyQuestions: (surveyId: string, questionIds: string[]) =>
    request<Survey>(`/api/surveys/${surveyId}/questions/reorder`, { label: "reorderSurveyQuestions", method: "POST", body: JSON.stringify({ question_ids: questionIds }) }),
  reviseSurvey: (surveyId: string, payload: { revision_request: string; report_context?: Record<string, unknown> }) =>
    request<SurveyRevisionResponse>(`/api/surveys/${surveyId}/revise`, { label: "reviseSurvey", method: "POST", body: JSON.stringify(payload) }),
  exportSurveyCsv: (surveyId: string) => textRequest(`/api/surveys/${surveyId}/export.csv`),
  exportSurveyResponseTemplateCsv: (surveyId: string) => textRequest(`/api/surveys/${surveyId}/response-template.csv`),
  exportSurveySampleResponsesCsv: (surveyId: string) => textRequest(`/api/surveys/${surveyId}/sample-responses.csv`),
  surveyAnalysis: (surveyId: string) => request<SurveyAnalysis>(`/api/surveys/${surveyId}/analysis`, { label: "surveyAnalysis", method: "GET" }),
  uploadSurveyResponses: (surveyId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return uploadRequest<SurveyUploadResponse>(`/api/surveys/${surveyId}/responses/upload`, formData);
  },
  uploadAdHocSurveyResponses: (taskId: string, runId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return uploadRequest<SurveyUploadResponse>(`/api/tasks/${taskId}/runs/${runId}/survey/responses/upload-any`, formData);
  },
  importTaskSurveyCsv: (taskId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return uploadRequest<SurveyUploadResponse>(`/api/tasks/${taskId}/survey/import-feedback`, formData);
  },
  llmStatus: () => request<LlmStatus>("/api/llm/status", { label: "llmStatus", method: "GET" }),
  testLlm: () => request<LlmStatus>("/api/llm/test", { label: "testLlm", method: "POST" }),
  collectorStatus: () => request<CollectorStatus>("/api/search/status", { label: "collectorStatus", method: "GET" }),
  testSearch: (query: string) => request<SearchTestResult>("/api/search/test", { label: "testSearch", method: "POST", body: JSON.stringify({ query }) })
};
