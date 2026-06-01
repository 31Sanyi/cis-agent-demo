import csv
import re
from io import StringIO

from app.schemas.survey import Survey

SURVEY_TEMPLATE_COLUMNS = [
    "question_id",
    "field_name",
    "question_text",
    "question_type",
    "options",
    "required",
    "analysis_goal",
    "related_claim_id",
]


def export_survey_template_csv(survey: Survey) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=SURVEY_TEMPLATE_COLUMNS)
    writer.writeheader()
    for question in survey.questions:
        writer.writerow(
            {
                "question_id": question.question_id,
                "field_name": question.field_name,
                "question_text": question.question_text,
                "question_type": question.question_type,
                "options": "|".join(question.options),
                "required": "true" if question.required else "false",
                "analysis_goal": question.analysis_goal,
                "related_claim_id": question.related_claim_id or "",
            }
        )
    return output.getvalue()


def export_survey_response_template_csv(survey: Survey) -> str:
    output = StringIO()
    field_names = ["respondent_id"] + [question.field_name for question in survey.questions]
    writer = csv.DictWriter(output, fieldnames=field_names)
    writer.writeheader()
    return output.getvalue()


def response_field_name(question) -> str:
    text = re.sub(r"\s+", "", question.question_text)
    text = re.sub(r"[^\w\u4e00-\u9fff]", "", text)
    short_text = text[:12] or question.field_name
    return f"{question.question_id}_{short_text}"
