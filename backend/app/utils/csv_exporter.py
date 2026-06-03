import csv
import re
from io import StringIO

from app.schemas.survey import Survey

SURVEY_TEMPLATE_COLUMNS = [
    "section_id",
    "section_title",
    "question_id",
    "question_text",
    "question_type",
    "options",
    "required",
]

QUESTION_TYPE_LABELS = {
    "single_choice": "单选题",
    "multiple_choice": "多选题",
    "rating": "评分题",
    "text": "开放题",
    "number": "数字题",
}


def export_survey_template_csv(survey: Survey) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=SURVEY_TEMPLATE_COLUMNS)
    writer.writeheader()
    for question in survey.questions:
        writer.writerow(
            {
                "section_id": "",
                "section_title": "",
                "question_id": question.question_id,
                "question_text": question.question_text,
                "question_type": QUESTION_TYPE_LABELS.get(question.question_type, question.question_type),
                "options": "|".join(question.options),
                "required": "true" if question.required else "false",
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
