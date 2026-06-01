export type Task = {
  task_id: string;
  product_name: string;
  competitors: string[];
  region: string;
  industry: string;
  status: string;
  rework_count: number;
  created_at: string;
  updated_at: string;
};

export type TaskRun = {
  run_id: string;
  task_id: string;
  workflow_engine: string;
  collector_mode: string;
  analyst_mode: string;
  writer_mode: string;
  content_mode?: string | null;
  demo_mode: string;
  auto_rework: boolean;
  status: string;
  final_status?: string | null;
  started_at: string;
  finished_at?: string | null;
  elapsed_time_ms?: number | null;
  error_message?: string | null;
  created_at: string;
};

export type Evidence = {
  evidence_id: string;
  run_id?: string | null;
  competitor?: string;
  source_type: string;
  url?: string;
  local_ref?: string;
  snippet: string;
  confidence: number;
  source_domain?: string;
  source_quality?: "official" | "documentation" | "media" | "review" | "unknown" | "low_quality";
  relevance_score?: number;
  relevance_level?: "high" | "medium" | "low" | "unrelated";
  relevance_reason?: string;
  entity_match_signals?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  content_mode?: "snippet" | "page";
  page_fetch_success?: boolean;
  page_title?: string | null;
  content_excerpt?: string | null;
  content_chars?: number | null;
  fetch_status_code?: number | null;
  page_fetch_error?: string | null;
  fetched_at?: string | null;
  collected_at: string;
};

export type Claim = {
  claim_id: string;
  competitor?: string;
  text: string;
  category: string;
  evidence_ids: string[];
  confidence: number;
};

export type SwotItem = {
  summary: string;
  competitor?: string | null;
  evidence_ids: string[];
  confidence: number;
};

export type SwotAnalysis = {
  strengths: SwotItem[];
  weaknesses: SwotItem[];
  opportunities: SwotItem[];
  threats: SwotItem[];
};

export type Report = {
  report_id: string;
  task_id: string;
  run_id?: string | null;
  markdown: string;
  json_report: {
    knowledge?: Record<string, unknown>;
    swot?: SwotAnalysis;
    planner?: {
      intent_classification?: string | null;
      selected_dimensions?: string[];
      writer_guidance?: string[];
    };
    claims?: Claim[];
    writer_diagnostics?: WriterDiagnostics;
  };
  claims: Claim[];
  qa_result?: QaResult;
};

export type WriterDiagnostics = {
  writer_mode_requested?: string;
  writer_mode_used?: string;
  llm_enabled?: boolean;
  llm_provider?: string;
  llm_model?: string;
  llm_base_url_configured?: boolean;
  has_api_key?: boolean;
  llm_call_attempted?: boolean;
  llm_call_success?: boolean;
  llm_elapsed_time_ms?: number;
  llm_error_type?: string;
  llm_error_message?: string;
  llm_response_preview?: string;
  fallback_used?: boolean;
  llm_fallback_reason?: string;
  selected_dimensions?: string[];
  writer_guidance_count?: number;
  intent_classification?: string | null;
};

export type LlmStatus = {
  llm_provider: string;
  llm_model: string;
  base_url_configured: boolean;
  api_key_configured: boolean;
  llm_enabled: boolean;
  last_check_status: "not_checked" | "success" | "failed";
  last_error?: string | null;
  suggested_action: string;
};

export type CollectorStatus = {
  search_provider: string;
  api_key_configured: boolean;
  base_url_configured: boolean;
  timeout: number;
  max_results: number;
  enabled: boolean;
};

export type SearchTestResult = {
  success: boolean;
  provider: string;
  query: string;
  result_count: number;
  results_preview: Array<{ title: string; url: string; snippet: string }>;
  error_type?: string | null;
  error_message?: string | null;
};

export type WorkflowSummary = {
  run_id?: string;
  task_id?: string;
  workflow_engine_requested?: string;
  workflow_engine_used?: string;
  intent_classification?: string | null;
  ambiguity_level?: string | null;
  scope_type?: string | null;
  scope_size?: string | null;
  survey_needed?: boolean;
  survey_recommended?: boolean;
  node_sequence?: string[];
  conditional_routes_taken?: Array<{ from_node?: string; to_node?: string; reason?: string; rework_count?: number; final_status?: string }>;
  rework_count?: number;
  final_status?: string;
  elapsed_time_ms?: number;
  error_message?: string | null;
  run_isolation_strategy?: string;
  run_cleanup_summary?: Record<string, unknown>;
  evidence_gate_output?: {
    evidence_gate_passed?: boolean;
    missing_relevant_evidence_competitors?: string[];
    relevant_evidence_count_by_competitor?: Record<string, number>;
    unrelated_evidence_count_by_competitor?: Record<string, number>;
    suggested_route?: string | null;
    suggested_action?: string;
  };
  selected_dimensions?: string[];
  recommended_next_constraints?: string[];
  clarification_targets?: string[];
  candidate_competitors?: Array<{
    name?: string;
    reason?: string;
    confidence?: number;
    rationale?: string;
    source?: string;
    priority?: number;
    metadata?: Record<string, unknown>;
  }>;
  planning_stages?: Array<{
    stage_id?: string;
    label?: string;
    objective?: string;
    outputs?: string[];
    depends_on?: string[];
    description?: string;
    status?: string;
    priority?: number;
    metadata?: Record<string, unknown>;
  }>;
  downstream_guidance?: {
    collector?: string[];
    analyst?: string[];
    writer?: string[];
    qa?: string[];
    survey?: string[];
  } | null;
  swot_analysis?: SwotAnalysis | null;
  page_fetch_output?: {
    page_fetch_provider?: string;
    page_fetch_attempted?: boolean;
    page_fetch_attempt_count?: number;
    page_fetch_success_count?: number;
    page_fetch_failed_count?: number;
    page_fetch_skipped_count?: number;
    page_fetch_fallback_count?: number;
    page_fetch_error_summary?: Record<string, number>;
    avg_content_chars?: number;
    max_content_chars?: number;
    fetched_evidence_ids?: string[];
    skipped_evidence_ids?: string[];
    run_id?: string | null;
  };
};

export type CollectorDiagnostics = {
  collector_mode_requested?: string;
  collector_mode_used?: string;
  web_search_attempted?: boolean;
  web_search_success?: boolean;
  query_count?: number;
  evidence_count?: number;
  fallback_used?: boolean;
  fallback_reason?: string;
  elapsed_time_ms?: number;
  planner_query_hints_used?: boolean;
  targeted_recollection_used?: boolean;
  planner_hint_query_count_by_competitor?: Record<string, number>;
  targeted_query_count_by_competitor?: Record<string, number>;
  effective_query_count_by_competitor?: Record<string, number>;
  effective_queries_preview_by_competitor?: Record<string, string[]>;
  targeted_queries_preview_by_competitor?: Record<string, string[]>;
};

export type QaResult = {
  task_id: string;
  run_id?: string | null;
  status: "passed" | "failed" | "manual_review";
  hard_errors: string[];
  soft_suggestions: string[];
  rework_instructions: Array<{
    target_agent: string;
    error_type: string;
    reason: string;
    suggested_action: string;
    claim_id?: string;
    failed_claim?: string;
    failed_schema?: string;
    metadata?: Record<string, unknown>;
  }>;
  rework_history: Array<{
    round: number;
    from_status: string;
    error_type: string;
    route_to?: string;
    action: string;
    result_status?: string;
  }>;
  route_to?: string;
  rework_count: number;
  metadata?: {
    swot_validation?: {
      status?: string;
      issue_count?: number;
      issues?: Array<{
        error_type?: string;
        target_agent?: string;
        competitor?: string | null;
        quadrant?: string | null;
        fix_type?: string;
        reason?: string;
        suggested_action?: string;
        query_focus?: string[];
        focus_dimensions?: string[];
      }>;
    };
  };
};

export type TraceRecord = {
  trace_id: string;
  task_id: string;
  run_id?: string | null;
  agent_name: string;
  input_summary: string;
  output_summary: string;
  schema_validation_result: string;
  elapsed_time_ms: number;
  retry_count: number;
  error_message?: string;
  model_name?: string;
  token_usage?: number;
};

export type Dag = {
  nodes: Array<{ id: string; label: string; status: string }>;
  edges: Array<{ source: string; target: string; label: string }>;
};

export type SurveyMetricRole =
  | "background"
  | "pain_existence"
  | "pain_frequency"
  | "pain_severity"
  | "pain_priority"
  | "switching_risk"
  | "competitor_preference"
  | "solution_preference"
  | "willingness_to_pay"
  | "open_feedback";

export type SurveyPainPoint = {
  pain_id: string;
  pain_point: string;
  source_from_report: string;
  related_claim_ids: string[];
  related_competitors: string[];
  affected_user_scenarios: string[];
  severity_assumption?: string | null;
  confidence: number;
  why_need_survey: string;
  research_questions: string[];
  metadata: Record<string, unknown>;
};

export type SurveyQuestion = {
  question_id: string;
  survey_id: string;
  field_name: string;
  question_text: string;
  question_type: "single_choice" | "multiple_choice" | "rating" | "text" | "number";
  options: string[];
  required: boolean;
  analysis_goal: string;
  related_claim_id?: string | null;
  reason: string;
  order: number;
  theme?: string | null;
  hypothesis?: string | null;
  maps_to_pain_id?: string | null;
  research_purpose?: string | null;
  analysis_method?: string | null;
  metric_role?: SurveyMetricRole | null;
};

export type Survey = {
  survey_id: string;
  task_id: string;
  run_id: string;
  title: string;
  description: string;
  target_respondents: string;
  research_goal: string;
  status: string;
  version: number;
  source_claim_ids: string[];
  questions: SurveyQuestion[];
  pain_points: SurveyPainPoint[];
  question_pain_mapping: Record<string, string>;
  planner_snapshot: Record<string, unknown>;
  report_context_snapshot: Record<string, unknown>;
  expected_analysis_dimensions: string[];
  csv_columns: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type SurveyQuestionCreate = {
  field_name?: string | null;
  question_text: string;
  question_type: SurveyQuestion["question_type"];
  options?: string[];
  required?: boolean;
  analysis_goal?: string;
  related_claim_id?: string | null;
  reason?: string;
  theme?: string | null;
  hypothesis?: string | null;
  maps_to_pain_id?: string | null;
  research_purpose?: string | null;
  analysis_method?: string | null;
  metric_role?: SurveyMetricRole | null;
};

export type SurveyUpdateRequest = {
  title?: string;
  description?: string;
  target_respondents?: string;
  research_goal?: string;
  expected_analysis_dimensions?: string[];
  questions?: Array<Partial<SurveyQuestion> & { question_id: string }>;
};

export type SurveyTopicGenerateRequest = {
  topic: string;
  target_respondents?: string;
  research_goal?: string;
  requirements?: string;
  question_count?: number;
};

export type SurveyRevisionResponse = {
  revision_summary: string;
  survey: Survey;
  removed_questions: Array<{ question_id: string; reason: string }>;
  added_questions: Array<{ question_id: string; reason: string }>;
};

export type SurveyAnalysis = {
  analysis_id: string;
  survey_id: string;
  batch_id: string;
  summary: string;
  executive_summary?: string | null;
  sample_summary: Record<string, unknown>;
  key_findings: Array<Record<string, unknown>>;
  question_level_analysis: Array<Record<string, unknown>>;
  claim_updates: Array<Record<string, unknown>>;
  user_pain_points: string[];
  pain_point_validation?: Array<Record<string, unknown>>;
  pain_point_ranking?: Array<Record<string, unknown>>;
  claim_validation_matrix?: Array<Record<string, unknown>>;
  segment_insights?: Array<Record<string, unknown>>;
  competitor_switching_analysis?: Array<Record<string, unknown>>;
  pricing_and_wtp_analysis?: Record<string, unknown> | null;
  recommended_report_revisions?: Array<Record<string, unknown>>;
  next_research_questions?: string[];
  willingness_to_pay?: string | null;
  switching_risk?: string | null;
  survey_evidence: Record<string, unknown>;
  question_summaries?: Array<Record<string, unknown>>;
  hypothesis_findings?: Array<Record<string, unknown>>;
  limitations?: string[];
  dashboard_summary: string;
  created_at: string;
};

export type SurveyUploadResponse = {
  batch_id: string;
  analysis_id: string;
  sample_size: number;
  valid_count: number;
  invalid_count: number;
  analysis_summary: string;
  raw_stats: Record<string, unknown>;
  analysis: SurveyAnalysis;
  survey?: Survey | null;
  survey_evidence?: Record<string, unknown> | null;
  evidence?: Evidence | null;
  question_summaries?: Array<Record<string, unknown>>;
  hypothesis_findings?: Array<Record<string, unknown>>;
  overall_summary?: string;
  limitations?: string[];
};

export type SurveyPlannerContext = {
  task: Task;
  planner_context: {
    intent_classification: string;
    survey_needed: boolean;
    survey_recommended?: boolean;
    survey_objective?: string | null;
    survey_inputs?: {
      objective?: string | null;
      respondent_type?: string | null;
      question_themes: string[];
      hypotheses: string[];
      metadata: Record<string, unknown>;
    } | null;
    extracted_context: Record<string, unknown>;
    selected_dimensions: string[];
    downstream_guidance?: {
      survey?: string[] | null;
    } | null;
  };
};
