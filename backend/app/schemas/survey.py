from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

SurveyStatus = Literal["draft", "revised", "exported", "responses_uploaded", "analyzed"]
SurveyQuestionType = Literal["single_choice", "multiple_choice", "rating", "text", "number"]
SurveyMetricRole = Literal[
    "background",
    "pain_existence",
    "pain_frequency",
    "pain_severity",
    "pain_priority",
    "switching_risk",
    "competitor_preference",
    "solution_preference",
    "willingness_to_pay",
    "open_feedback",
]


class SurveyPainPoint(BaseModel):
    pain_id: str = Field(min_length=1)
    pain_point: str = Field(min_length=1)
    source_from_report: str = ""
    related_claim_ids: list[str] = Field(default_factory=list)
    related_competitors: list[str] = Field(default_factory=list)
    affected_user_scenarios: list[str] = Field(default_factory=list)
    severity_assumption: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    why_need_survey: str = ""
    research_questions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SurveyQuestion(BaseModel):
    question_id: str = Field(min_length=1)
    survey_id: str = ""
    field_name: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    question_type: SurveyQuestionType
    options: list[str] = Field(default_factory=list)
    required: bool = True
    analysis_goal: str = Field(min_length=1)
    related_claim_id: str | None = None
    maps_to_pain_id: str | None = None
    research_purpose: str | None = None
    analysis_method: str | None = None
    metric_role: SurveyMetricRole | None = None
    reason: str = Field(min_length=1)
    order: int = Field(ge=1)
    theme: str | None = None
    hypothesis: str | None = None

    @model_validator(mode="after")
    def validate_options(self) -> "SurveyQuestion":
        if self.question_type in {"single_choice", "multiple_choice", "rating"} and not self.options:
            raise ValueError(f"{self.question_type} questions require options")
        return self


class Survey(BaseModel):
    survey_id: str = Field(default_factory=lambda: f"survey_{uuid4().hex[:10]}")
    task_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    target_respondents: str = Field(min_length=1)
    research_goal: str = Field(min_length=1)
    status: SurveyStatus = "draft"
    version: int = Field(default=1, ge=1)
    source_claim_ids: list[str] = Field(default_factory=list)
    pain_points: list[SurveyPainPoint] = Field(default_factory=list)
    questions: list[SurveyQuestion] = Field(default_factory=list)
    question_pain_mapping: dict[str, str] = Field(default_factory=dict)
    planner_snapshot: dict[str, Any] = Field(default_factory=dict)
    report_context_snapshot: dict[str, Any] = Field(default_factory=dict)
    expected_analysis_dimensions: list[str] = Field(default_factory=list)
    csv_columns: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def validate_questions(self) -> "Survey":
        field_names = [question.field_name for question in self.questions]
        if len(field_names) != len(set(field_names)):
            raise ValueError("Survey question field_name values must be unique")
        for index, question in enumerate(self.questions, start=1):
            question.survey_id = self.survey_id
            question.order = question.order or index
        if not self.csv_columns:
            self.csv_columns = field_names
        self.question_pain_mapping = {
            question.question_id: question.maps_to_pain_id
            for question in self.questions
            if question.maps_to_pain_id
        }
        return self


class SurveyGenerateRequest(BaseModel):
    product_name: str = ""
    competitors: list[str] = Field(default_factory=list)
    industry: str = ""
    region: str = ""
    report_markdown: str = ""
    claims_json: list[dict[str, Any]] = Field(default_factory=list)
    uncertain_findings: list[str] = Field(default_factory=list)
    user_requirements: str = ""
    question_count: int = Field(default=10, ge=1, le=30)
    force_generate: bool = False


class SurveyReviseRequest(BaseModel):
    revision_request: str = Field(min_length=1)
    report_context: dict[str, Any] = Field(default_factory=dict)


class SurveyQuestionUpdate(BaseModel):
    question_id: str = Field(min_length=1)
    field_name: str | None = None
    question_text: str | None = None
    question_type: SurveyQuestionType | None = None
    options: list[str] | None = None
    required: bool | None = None
    analysis_goal: str | None = None
    related_claim_id: str | None = None
    maps_to_pain_id: str | None = None
    research_purpose: str | None = None
    analysis_method: str | None = None
    metric_role: SurveyMetricRole | None = None
    reason: str | None = None
    order: int | None = Field(default=None, ge=1)
    theme: str | None = None
    hypothesis: str | None = None


class SurveyQuestionCreate(BaseModel):
    field_name: str | None = None
    question_text: str = Field(default="请填写新的问卷问题", min_length=1)
    question_type: SurveyQuestionType = "single_choice"
    options: list[str] = Field(default_factory=lambda: ["选项 A", "选项 B", "其他"])
    required: bool = True
    analysis_goal: str = "分析该题反馈对研究问题的影响。"
    related_claim_id: str | None = None
    maps_to_pain_id: str | None = None
    research_purpose: str | None = None
    analysis_method: str | None = None
    metric_role: SurveyMetricRole | None = None
    reason: str = "由用户在问卷编辑器中手动新增。"
    theme: str | None = None
    hypothesis: str | None = None


class SurveyUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    target_respondents: str | None = None
    research_goal: str | None = None
    expected_analysis_dimensions: list[str] | None = None
    questions: list[SurveyQuestionUpdate] | None = None


class SurveyAddQuestionRequest(BaseModel):
    question: SurveyQuestionCreate = Field(default_factory=SurveyQuestionCreate)


class SurveyReorderRequest(BaseModel):
    question_ids: list[str] = Field(min_length=1)


class SurveyTopicGenerateRequest(BaseModel):
    topic: str = Field(min_length=1)
    target_respondents: str = ""
    research_goal: str = ""
    requirements: str = ""
    question_count: int = Field(default=10, ge=1, le=30)


class SurveyTaskRefineRequest(BaseModel):
    survey_id: str
    instruction: str = Field(min_length=1)


class SurveyRevisionResponse(BaseModel):
    revision_summary: str
    survey: Survey
    removed_questions: list[dict[str, str]] = Field(default_factory=list)
    added_questions: list[dict[str, str]] = Field(default_factory=list)


class SurveyResponseBatch(BaseModel):
    batch_id: str = Field(default_factory=lambda: f"batch_{uuid4().hex[:10]}")
    survey_id: str
    file_name: str
    sample_size: int = Field(ge=0)
    valid_count: int = Field(ge=0)
    invalid_count: int = Field(ge=0)
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    parse_status: Literal["pending", "success", "failed"] = "pending"
    error_message: str | None = None
    raw_stats: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SurveyAnalysis(BaseModel):
    analysis_id: str = Field(default_factory=lambda: f"analysis_{uuid4().hex[:10]}")
    survey_id: str
    batch_id: str
    summary: str
    executive_summary: str = ""
    sample_summary: dict[str, Any] = Field(default_factory=dict)
    key_findings: list[dict[str, Any]] = Field(default_factory=list)
    question_level_analysis: list[dict[str, Any]] = Field(default_factory=list)
    claim_updates: list[dict[str, Any]] = Field(default_factory=list)
    user_pain_points: list[str] = Field(default_factory=list)
    willingness_to_pay: str | None = None
    switching_risk: str | None = None
    survey_evidence: dict[str, Any] = Field(default_factory=dict)
    question_summaries: list[dict[str, Any]] = Field(default_factory=list)
    hypothesis_findings: list[dict[str, Any]] = Field(default_factory=list)
    pain_point_validation: list[dict[str, Any]] = Field(default_factory=list)
    pain_point_ranking: list[dict[str, Any]] = Field(default_factory=list)
    claim_validation_matrix: list[dict[str, Any]] = Field(default_factory=list)
    segment_insights: list[dict[str, Any]] = Field(default_factory=list)
    competitor_switching_analysis: dict[str, Any] = Field(default_factory=dict)
    pricing_and_wtp_analysis: dict[str, Any] = Field(default_factory=dict)
    recommended_report_revisions: list[dict[str, Any]] = Field(default_factory=list)
    next_research_questions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    dashboard_summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SurveyUploadResponse(BaseModel):
    batch_id: str
    analysis_id: str
    sample_size: int
    valid_count: int
    invalid_count: int
    analysis_summary: str
    raw_stats: dict[str, Any]
    analysis: SurveyAnalysis
    survey: Survey | None = None
    survey_evidence: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
    question_summaries: list[dict[str, Any]] = Field(default_factory=list)
    hypothesis_findings: list[dict[str, Any]] = Field(default_factory=list)
    overall_summary: str = ""
    limitations: list[str] = Field(default_factory=list)
