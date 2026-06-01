import csv
import re
from io import StringIO
from statistics import median
from typing import Any

from app.schemas.survey import Survey

MULTI_CHOICE_SPLIT_RE = re.compile(r"[,;；、|]\s*")


class SurveyCsvValidationError(ValueError):
    def __init__(self, missing_fields: list[str]):
        super().__init__("CSV 缺少必要字段")
        self.missing_fields = missing_fields


class SurveyCsvFormatError(ValueError):
    pass


def parse_survey_response_csv(content: str, survey: Survey) -> dict[str, Any]:
    fieldnames, rows = _read_csv_rows(content)
    required_fields = [question.field_name for question in survey.questions]
    missing = [field for field in required_fields if field not in fieldnames]
    if missing:
        raise SurveyCsvValidationError(missing)

    stats_by_question: dict[str, Any] = {}
    valid_count = 0
    invalid_count = 0

    for row in rows:
        row_valid = True
        for question in survey.questions:
            if question.required and not row.get(question.field_name):
                row_valid = False
                break
        if row_valid:
            valid_count += 1
        else:
            invalid_count += 1

    for question in survey.questions:
        answers = [row.get(question.field_name, "") for row in rows if row.get(question.field_name, "")]
        stats_by_question[question.question_id] = _question_stats(question, answers, len(rows))

    return {
        "sample_size": len(rows),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "csv_columns": fieldnames,
        "questions": stats_by_question,
    }


def infer_survey_from_csv(
    content: str,
    *,
    task_id: str,
    run_id: str,
    title: str = "自定义上传问卷分析",
    description: str = "根据上传 CSV 表头自动识别题目并进行统计分析。",
    target_respondents: str = "CSV 上传样本",
    research_goal: str = "分析用户上传的自定义问卷反馈。",
) -> Survey:
    fieldnames, rows = _read_csv_rows(content)
    questions = []
    for index, field_name in enumerate(fieldnames, start=1):
        answers = [row.get(field_name, "") for row in rows if row.get(field_name, "")]
        question_type, options = _infer_question_type(field_name, answers)
        questions.append(
            {
                "question_id": f"Q{index}",
                "field_name": field_name,
                "question_text": field_name,
                "question_type": question_type,
                "options": options,
                "required": False,
                "analysis_goal": f"分析“{field_name}”字段的用户反馈分布。",
                "related_claim_id": None,
                "reason": "该题目来自用户上传 CSV 表头，系统自动纳入自定义问卷分析。",
                "order": index,
            }
        )
    return Survey(
        task_id=task_id,
        run_id=run_id,
        title=title,
        description=description,
        target_respondents=target_respondents,
        research_goal=research_goal,
        status="responses_uploaded",
        questions=questions,
        expected_analysis_dimensions=["自定义问卷统计", "用户反馈摘要", "样本局限性"],
        csv_columns=fieldnames,
    )


def _question_stats(question, answers: list[str], sample_size: int) -> dict[str, Any]:
    base = {
        "question_id": question.question_id,
        "field_name": question.field_name,
        "question_text": question.question_text,
        "question_type": question.question_type,
        "answer_count": len(answers),
    }
    if question.question_type == "single_choice":
        distribution = _distribution(answers, sample_size)
        return {**base, "distribution": distribution, "top_option": _top_option(distribution)}
    if question.question_type == "multiple_choice":
        choices: list[str] = []
        for answer in answers:
            choices.extend([item.strip() for item in MULTI_CHOICE_SPLIT_RE.split(answer) if item.strip()])
        distribution = _distribution(choices, sample_size)
        return {**base, "distribution": distribution, "top_option": _top_option(distribution)}
    if question.question_type == "rating":
        numbers = _numbers(answers)
        return {**base, **_numeric_summary(numbers), "distribution": _distribution([str(int(number)) if number.is_integer() else str(number) for number in numbers], len(numbers))}
    if question.question_type == "number":
        return {**base, **_numeric_summary(_numbers(answers))}
    return {**base, "text_samples": answers[:20]}


def _read_csv_rows(content: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(StringIO(content.lstrip("\ufeff")))
    raw_fieldnames = reader.fieldnames or []
    fieldnames = [(field or "").strip() for field in raw_fieldnames]
    if not fieldnames or any(not field for field in fieldnames):
        raise SurveyCsvFormatError("CSV 表头不能为空")
    duplicates = sorted({field for field in fieldnames if fieldnames.count(field) > 1})
    if duplicates:
        raise SurveyCsvFormatError(f"CSV 表头存在重复字段：{', '.join(duplicates)}")

    rows = []
    for row in reader:
        normalized = {
            field_name: (row.get(raw_fieldname) or "").strip()
            for raw_fieldname, field_name in zip(raw_fieldnames, fieldnames, strict=False)
        }
        if any(value for value in normalized.values()):
            rows.append(normalized)
    return fieldnames, rows


def _infer_question_type(field_name: str, answers: list[str]) -> tuple[str, list[str]]:
    if not answers:
        return "text", []

    if _looks_like_text_field(field_name):
        return "text", []

    if _looks_like_multiple_choice(field_name, answers):
        choices: list[str] = []
        for answer in answers:
            choices.extend([item.strip() for item in MULTI_CHOICE_SPLIT_RE.split(answer) if item.strip()])
        return "multiple_choice", _unique_values(choices)[:30]

    numbers = _numbers(answers)
    if len(numbers) == len(answers):
        if _looks_like_rating(field_name, numbers):
            return "rating", [_format_number(number) for number in sorted(set(numbers))]
        return "number", []

    unique_answers = _unique_values(answers)
    avg_len = sum(len(answer) for answer in answers) / len(answers)
    if avg_len <= 24 and len(unique_answers) <= max(12, int(len(answers) * 0.6)):
        return "single_choice", unique_answers[:30]
    return "text", []


def _looks_like_multiple_choice(field_name: str, answers: list[str]) -> bool:
    if _looks_like_text_field(field_name):
        return False
    split_answers = [answer for answer in answers if len(MULTI_CHOICE_SPLIT_RE.split(answer)) > 1]
    if not split_answers:
        return False
    avg_len = sum(len(answer) for answer in split_answers) / len(split_answers)
    return avg_len <= 40 and len(split_answers) >= max(1, int(len(answers) * 0.2))


def _looks_like_text_field(field_name: str) -> bool:
    return _contains_any(field_name, ["开放", "建议", "反馈", "评价", "comment", "feedback", "open"])


def _looks_like_rating(field_name: str, numbers: list[float]) -> bool:
    if not numbers:
        return False
    if min(numbers) < 0 or max(numbers) > 10:
        return False
    if _contains_any(field_name, ["评分", "满意", "重要", "兴趣", "score", "rating", "satisfaction", "importance"]):
        return True
    return len(set(numbers)) <= 10 and all(number.is_integer() for number in numbers)


def _contains_any(text: str, needles: list[str]) -> bool:
    normalized = text.lower()
    return any(needle.lower() in normalized for needle in needles)


def _unique_values(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _format_number(number: float) -> str:
    return str(int(number)) if number.is_integer() else str(number)


def _distribution(values: list[str], denominator: int) -> dict[str, dict[str, float | int]]:
    result: dict[str, dict[str, float | int]] = {}
    for value in values:
        result.setdefault(value, {"count": 0, "ratio": 0.0})
        result[value]["count"] += 1
    for value in result.values():
        value["ratio"] = round(value["count"] / denominator, 4) if denominator else 0.0
    return result


def _top_option(distribution: dict[str, dict[str, float | int]]) -> str | None:
    if not distribution:
        return None
    return max(distribution.items(), key=lambda item: int(item[1]["count"]))[0]


def _numbers(answers: list[str]) -> list[float]:
    numbers: list[float] = []
    for answer in answers:
        try:
            numbers.append(float(answer))
        except ValueError:
            continue
    return numbers


def _numeric_summary(numbers: list[float]) -> dict[str, float | None]:
    if not numbers:
        return {"average": None, "median": None, "min": None, "max": None}
    return {
        "average": round(sum(numbers) / len(numbers), 4),
        "median": median(numbers),
        "min": min(numbers),
        "max": max(numbers),
    }
