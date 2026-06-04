from __future__ import annotations

import csv
import re
from io import StringIO
from typing import Any

from app.schemas.survey import Survey, SurveyCleaningResult, SurveyDataQualityAssessment
from app.utils.csv_parser import parse_survey_response_csv

LOW_INFO_TEXTS = {
    "",
    "无",
    "没有",
    "不知道",
    "不清楚",
    "随便",
    "test",
    "testing",
    "asdf",
    "111",
    "123",
    "n/a",
    "na",
    "none",
    "-",
    ".",
}
SEGMENT_FIELD_MARKERS = ("segment", "persona", "user_type", "role", "职业", "岗位", "身份", "人群", "用户类型")
RATING_FIELD_MARKERS = ("评分", "满意", "重要", "频率", "severity", "rating", "score", "satisfaction", "importance")


class SurveyResponseCleaningService:
    def clean(self, survey: Survey, raw_stats: dict[str, Any], ingestion: Any | None = None) -> SurveyCleaningResult:
        rows = list(raw_stats.get("response_rows") or [])
        questions = list(survey.questions or [])
        raw_count = len(rows) or int(raw_stats.get("sample_size") or 0)
        required_fields = [question.field_name for question in questions if question.required]
        field_names = [question.field_name for question in questions]

        excluded: list[dict[str, Any]] = []
        preview: list[dict[str, Any]] = []
        kept_rows: list[dict[str, str]] = []
        seen_respondents: set[str] = set()
        seen_signatures: set[tuple[tuple[str, str], ...]] = set()
        suspicious_count = 0
        target_mismatch_count = 0
        completeness_scores: list[float] = []

        for index, row in enumerate(rows, start=1):
            normalized = {field: str(row.get(field, "") or "").strip() for field in field_names}
            answered_count = sum(1 for value in normalized.values() if value)
            non_empty_ratio = answered_count / max(len(field_names), 1)
            respondent_id = str(row.get("respondent_id") or row.get("Respondent ID") or "").strip()
            row_flags: list[str] = []
            exclude_reasons: list[str] = []

            if answered_count <= 1 or non_empty_ratio <= 0.1:
                exclude_reasons.append("blank_response")

            missing_required = sum(1 for field in required_fields if not normalized.get(field))
            required_missing_ratio = missing_required / max(len(required_fields), 1) if required_fields else 0.0
            if required_fields and required_missing_ratio > 0.5:
                exclude_reasons.append("required_fields_missing")

            if respondent_id:
                if respondent_id in seen_respondents:
                    exclude_reasons.append("duplicate_respondent_id")
                else:
                    seen_respondents.add(respondent_id)

            signature = tuple(sorted(normalized.items()))
            if signature in seen_signatures:
                exclude_reasons.append("duplicate_response_pattern")
            else:
                seen_signatures.add(signature)

            low_info_text_fields = []
            for question in questions:
                if question.question_type != "text":
                    continue
                value = normalized.get(question.field_name, "")
                if value and self._is_low_info_text(value):
                    low_info_text_fields.append(question.field_name)
            if low_info_text_fields:
                row_flags.append("low_information_text")
                if answered_count <= max(2, len(low_info_text_fields)):
                    exclude_reasons.append("low_information_only")

            rating_values = self._rating_values(questions, normalized)
            if len(rating_values) >= 3 and len(set(rating_values)) == 1:
                row_flags.append("straight_lining")

            if self._target_mismatch_detected(survey.target_respondents, normalized):
                row_flags.append("target_mismatch")

            completeness = 1.0 - required_missing_ratio if required_fields else non_empty_ratio

            if exclude_reasons:
                excluded.append(
                    {
                        "row_number": index,
                        "respondent_id": respondent_id or None,
                        "reasons": exclude_reasons,
                        "answered_count": answered_count,
                    }
                )
                preview.append(
                    {
                        "row_number": index,
                        "respondent_id": respondent_id or None,
                        "status": "excluded",
                        "reasons": exclude_reasons,
                        "flags": row_flags,
                    }
                )
                continue

            if "straight_lining" in row_flags:
                suspicious_count += 1
            if "target_mismatch" in row_flags:
                target_mismatch_count += 1
            completeness_scores.append(max(0.0, min(1.0, completeness)))
            kept_rows.append(normalized)
            preview.append(
                {
                    "row_number": index,
                    "respondent_id": respondent_id or None,
                    "status": "kept",
                    "flags": row_flags,
                    "answered_count": answered_count,
                }
            )

        clean_count = len(kept_rows)
        removed_count = max(raw_count - clean_count, 0)
        valid_ratio = round(clean_count / raw_count, 4) if raw_count else 0.0
        completeness_score = round(sum(completeness_scores) / len(completeness_scores), 4) if completeness_scores else 0.0
        sample_size_score = min(clean_count / 30, 1.0)
        consistency_penalty = 0.0
        if clean_count:
            consistency_penalty += 0.5 * (suspicious_count / clean_count)
            consistency_penalty += 0.5 * (target_mismatch_count / clean_count)
        consistency_score = max(0.0, 1.0 - consistency_penalty)
        quality_score = min(
            1.0,
            max(
                0.0,
                0.35 * sample_size_score
                + 0.30 * valid_ratio
                + 0.20 * completeness_score
                + 0.15 * consistency_score,
            ),
        )
        quality_level = self._quality_level(quality_score)
        can_enter_knowledge_base = clean_count >= 10 and quality_score >= 0.6 and valid_ratio >= 0.5

        reasons: list[str] = []
        warnings = list(raw_stats.get("parse_warnings") or [])
        if clean_count < 10:
            reasons.append("有效样本少于 10 条，暂不适合沉淀为知识库结论。")
        if valid_ratio < 0.5:
            reasons.append("清洗后有效率低于 50%，当前样本稳定性不足。")
        if quality_score < 0.6:
            reasons.append("综合质量评分低于知识库沉淀门槛。")
        if suspicious_count:
            warnings.append(f"{suspicious_count} 条样本存在评分题直线作答特征，已保留但降级可信度。")
        if target_mismatch_count:
            warnings.append(f"{target_mismatch_count} 条样本与目标受访者描述可能不匹配，建议人工复核。")
        if excluded:
            warnings.append(f"共剔除 {len(excluded)} 条样本，详情见剔除原因摘要。")

        clean_stats = self._rebuild_clean_stats(survey, kept_rows, raw_stats)
        clean_stats["data_quality_assessment"] = {
            "raw_count": raw_count,
            "clean_count": clean_count,
            "removed_count": removed_count,
            "valid_ratio": valid_ratio,
            "quality_score": round(quality_score, 4),
            "quality_level": quality_level,
            "can_enter_knowledge_base": can_enter_knowledge_base,
        }
        clean_stats["excluded_rows_summary"] = excluded[:20]
        clean_stats["cleaning_rules_applied"] = self._cleaning_rules_applied()
        clean_stats["source_type"] = raw_stats.get("source_type")
        clean_stats["file_name"] = raw_stats.get("file_name")

        return SurveyCleaningResult(
            data_quality=SurveyDataQualityAssessment(
                raw_count=raw_count,
                clean_count=clean_count,
                removed_count=removed_count,
                valid_ratio=valid_ratio,
                quality_score=round(quality_score, 4),
                quality_level=quality_level,
                can_enter_knowledge_base=can_enter_knowledge_base,
                reasons=reasons,
                warnings=warnings,
                excluded_rows_summary=excluded[:20],
                cleaning_rules_applied=self._cleaning_rules_applied(),
            ),
            clean_stats=clean_stats,
            cleaning_preview=preview[:20],
        )

    @staticmethod
    def _rebuild_clean_stats(survey: Survey, rows: list[dict[str, str]], raw_stats: dict[str, Any]) -> dict[str, Any]:
        if not rows:
            empty_questions = {}
            for question in survey.questions:
                empty_questions[question.question_id] = {
                    "question_id": question.question_id,
                    "field_name": question.field_name,
                    "question_text": question.question_text,
                    "question_type": question.question_type,
                    "answer_count": 0,
                }
            return {
                "sample_size": 0,
                "valid_count": 0,
                "invalid_count": 0,
                "csv_columns": list(raw_stats.get("csv_columns") or [question.field_name for question in survey.questions]),
                "questions": empty_questions,
                "response_rows": [],
            }
        output = StringIO()
        fieldnames = list(raw_stats.get("csv_columns") or [question.field_name for question in survey.questions])
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
        clean_stats = parse_survey_response_csv(output.getvalue(), survey)
        clean_stats["response_rows"] = rows
        return clean_stats

    @staticmethod
    def _cleaning_rules_applied() -> list[str]:
        return [
            "exclude_blank_response",
            "exclude_required_field_missing",
            "exclude_duplicate_respondent_id",
            "exclude_duplicate_response_pattern",
            "flag_low_information_text",
            "flag_straight_lining",
            "flag_target_mismatch",
            "apply_sample_size_and_valid_ratio_gate",
        ]

    @staticmethod
    def _quality_level(score: float) -> str:
        if score >= 0.8:
            return "high"
        if score >= 0.6:
            return "medium"
        if score >= 0.35:
            return "low"
        return "unusable"

    @staticmethod
    def _is_low_info_text(value: str) -> bool:
        normalized = re.sub(r"\s+", "", value.strip().lower())
        if normalized in LOW_INFO_TEXTS:
            return True
        return bool(re.fullmatch(r"(.)\1{2,}", normalized))

    @staticmethod
    def _rating_values(questions: list[Any], row: dict[str, str]) -> list[str]:
        values: list[str] = []
        for question in questions:
            if question.question_type == "rating" or any(marker in question.field_name.lower() for marker in RATING_FIELD_MARKERS):
                value = row.get(question.field_name, "")
                if value:
                    values.append(value)
        return values

    @staticmethod
    def _target_mismatch_detected(target_respondents: str, row: dict[str, str]) -> bool:
        target = str(target_respondents or "").lower()
        if not target:
            return False
        for field, value in row.items():
            field_lower = field.lower()
            if not any(marker in field_lower for marker in SEGMENT_FIELD_MARKERS):
                continue
            answer = str(value or "").lower()
            if not answer:
                continue
            if "学生" in target and any(token in answer for token in ("职场", "员工", "上班族", "manager", "employee", "teacher")):
                return True
            if any(token in target for token in ("企业", "职场", "员工")) and any(token in answer for token in ("学生", "student")):
                return True
        return False
