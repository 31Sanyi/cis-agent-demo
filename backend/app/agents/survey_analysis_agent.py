import json
from typing import Any

from app.services.survey_llm_client import SurveyLLMClient

SURVEY_ANALYSIS_SYSTEM_PROMPT = """你是竞品分析系统中的 SurveyAnalysisAgent。
你的任务是基于已清洗后的问卷反馈统计结果，判断产品痛点、竞品切换风险、付费意愿和原报告 claims 是否被用户侧样本支持。
问卷数据只能代表当前上传样本，不能直接代表整体市场。你必须区分强结论、弱信号、不可用数据和需要继续验证的问题。
如果 data_quality_assessment.can_enter_knowledge_base=false，你必须降低所有 knowledge_candidates 的 should_write_to_kb，并明确 rejection_reason。
输出必须是合法 JSON。"""


class SurveyAnalysisAgent:
    def __init__(self, llm_client: SurveyLLMClient | None = None):
        self.llm_client = llm_client or SurveyLLMClient()

    def analyze(
        self,
        survey_json: dict[str, Any],
        survey_stats_json: dict[str, Any],
        report_context: dict[str, Any],
    ) -> dict[str, Any]:
        return self.llm_client.generate_json(
            SURVEY_ANALYSIS_SYSTEM_PROMPT,
            build_survey_analysis_prompt(survey_json, survey_stats_json, report_context),
        ).data


def build_survey_analysis_prompt(
    survey_json: dict[str, Any],
    survey_stats_json: dict[str, Any],
    report_context: dict[str, Any],
) -> str:
    return f"""【原始问卷结构】
{json.dumps(survey_json, ensure_ascii=False)}
【pain_points】
{json.dumps(survey_json.get("pain_points", []), ensure_ascii=False)}
【question_pain_mapping】
{json.dumps(survey_json.get("question_pain_mapping", {}), ensure_ascii=False)}
【数据质量评估】
{json.dumps(survey_stats_json.get("data_quality_assessment", {}), ensure_ascii=False)}
【清洗后的统计结果】
{json.dumps(survey_stats_json, ensure_ascii=False)}
【被剔除样本原因摘要】
{json.dumps(survey_stats_json.get("excluded_rows_summary", []), ensure_ascii=False)}
【清洗规则】
{json.dumps(survey_stats_json.get("cleaning_rules_applied", []), ensure_ascii=False)}
【样本量】
{survey_stats_json.get("sample_size", 0)}
【PlannerAgent 快照】
{json.dumps(survey_json.get("planner_snapshot", {}), ensure_ascii=False)}
【原竞品分析报告】
{report_context.get("report_markdown", "")}
【原报告关键 Claims】
{json.dumps(report_context.get("claims_json", []), ensure_ascii=False)}

分析要求：
1. 判断每个 pain point 是否被当前样本支持、削弱、反驳或仍不确定。
2. 对每道关键问题给出统计解释。
3. 输出 pain_point_validation、pain_point_ranking、claim_validation_matrix。
4. 判断哪些原报告结论需要修正或谨慎表达。
5. 输出用户痛点、付费意愿、替代意愿、满意度等维度洞察。
6. 明确指出样本局限，不要过度推断。
7. 给出可以进入最终报告的 SurveyEvidence 摘要。
8. 输出必须是合法 JSON，不要输出 Markdown。

输出格式必须严格为：
{{
  "executive_summary": "string",
  "user_facing_summary": "给产品经理看的自然语言总结，150-300字。必须说明样本量、清洗后有效样本、最强痛点、最谨慎的结论和下一步建议。",
  "sample_summary": {{"sample_size": 0, "valid_count": 0, "limitations": ["string"]}},
  "key_findings": [
    {{"finding": "string", "supporting_questions": ["Q1"], "confidence": 0.0, "explanation": "string"}}
  ],
  "question_level_analysis": [
    {{"question_id": "Q1", "field_name": "string", "summary": "string", "notable_stats": ["string"]}}
  ],
  "claim_updates": [
    {{"claim_id": "string", "original_claim": "string", "survey_result": "string", "impact": "support | weaken | refine | no_clear_signal", "recommended_revision": "string"}}
  ],
  "user_pain_points": ["string"],
  "willingness_to_pay": "string",
  "switching_risk": "string",
  "survey_evidence": {{
    "snippet": "string",
    "confidence": 0.0,
    "metadata": {{"sample_size": 0, "source_type": "survey", "analysis_mode": "pain_point_validation"}}
  }},
  "pain_point_validation": [
    {{"pain_id": "P1", "pain_point": "string", "validation_result": "strongly_supported | partially_supported | not_supported | contradicted | inconclusive", "evidence_summary": "string", "frequency_score": 0.0, "severity_score": 0.0, "switching_risk_score": 0.0, "willingness_to_pay_score": 0.0, "priority_score": 0.0, "affected_segments": ["string"], "supporting_questions": ["Q1"], "recommended_report_update": "string", "confidence": 0.0}}
  ],
  "pain_point_ranking": [],
  "claim_validation_matrix": [],
  "segment_insights": [],
  "competitor_switching_analysis": {{}},
  "pricing_and_wtp_analysis": {{}},
  "recommended_report_revisions": [],
  "limitations": ["string"],
  "next_research_questions": ["string"],
  "dashboard_summary": "string",
  "data_quality_assessment": {{
    "raw_count": 0,
    "clean_count": 0,
    "removed_count": 0,
    "valid_ratio": 0.0,
    "quality_score": 0.0,
    "quality_level": "high | medium | low | unusable",
    "can_enter_knowledge_base": false,
    "reasons": ["string"],
    "warnings": ["string"],
    "excluded_rows_summary": [],
    "cleaning_rules_applied": ["string"]
  }},
  "knowledge_candidates": [
    {{
      "title": "string",
      "content": "string",
      "evidence_type": "survey_aggregate",
      "confidence": 0.0,
      "sample_size": 0,
      "clean_sample_size": 0,
      "supporting_questions": ["Q1"],
      "related_pain_ids": ["P1"],
      "related_claim_ids": ["claim_1"],
      "limitations": ["string"],
      "should_write_to_kb": false,
      "rejection_reason": "string or null"
    }}
  ],
  "cleaning_notes": ["string"]
}}"""
