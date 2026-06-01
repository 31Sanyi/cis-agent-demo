from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.survey import (
    SurveyAddQuestionRequest,
    SurveyGenerateRequest,
    SurveyReorderRequest,
    SurveyReviseRequest,
    SurveyTaskRefineRequest,
    SurveyTopicGenerateRequest,
    SurveyUpdateRequest,
)
from app.services.survey_llm_client import SurveyLLMClient
from app.services.survey_service import SurveyService, survey_error_response

router = APIRouter(prefix="/api")


@router.get("/survey/llm/status")
def survey_llm_status():
    return SurveyLLMClient().status()


@router.get("/tasks/{task_id}/survey/context")
def survey_planner_context(task_id: str, db: Session = Depends(get_db)):
    try:
        return SurveyService(db).planner_context_for_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


@router.post("/tasks/{task_id}/survey/generate")
def generate_task_survey(task_id: str, force_generate: bool = False, db: Session = Depends(get_db)):
    try:
        return SurveyService(db).generate_for_task(task_id, force_generate=force_generate)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except Exception as exc:  # noqa: BLE001
        status_code, payload = survey_error_response(exc)
        raise HTTPException(status_code=status_code, detail=payload) from exc


@router.post("/tasks/{task_id}/survey/refine")
def refine_task_survey(task_id: str, request: SurveyTaskRefineRequest, db: Session = Depends(get_db)):
    try:
        return SurveyService(db).refine_for_task(task_id, request.survey_id, request.instruction)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Survey not found") from exc
    except Exception as exc:  # noqa: BLE001
        status_code, payload = survey_error_response(exc)
        raise HTTPException(status_code=status_code, detail=payload) from exc


@router.get("/tasks/{task_id}/survey/export-csv")
def export_task_survey_csv(task_id: str, db: Session = Depends(get_db)):
    try:
        csv_content = SurveyService(db).export_response_csv_for_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except Exception as exc:  # noqa: BLE001
        status_code, payload = survey_error_response(exc)
        raise HTTPException(status_code=status_code, detail=payload) from exc
    return Response(
        content="\ufeff" + csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{task_id}_survey_response_template.csv"'},
    )


@router.post("/tasks/{task_id}/survey/import-csv")
@router.post("/tasks/{task_id}/survey/import-feedback")
async def import_task_survey_csv(task_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        raw_content = await file.read()
        return SurveyService(db).import_csv_for_task(task_id, file.filename or "responses", raw_content)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except Exception as exc:  # noqa: BLE001
        status_code, payload = survey_error_response(exc)
        raise HTTPException(status_code=status_code, detail=payload) from exc


@router.get("/tasks/{task_id}/survey/analysis")
def get_task_survey_analysis(task_id: str, db: Session = Depends(get_db)):
    try:
        analysis = SurveyService(db).latest_analysis_for_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    if analysis is None:
        return {"status": "no_survey_response_uploaded"}
    return analysis


@router.get("/tasks/{task_id}/runs/{run_id}/survey")
def latest_survey_for_run(task_id: str, run_id: str, db: Session = Depends(get_db)):
    survey = SurveyService(db).latest_for_run(task_id, run_id)
    if survey is None:
        raise HTTPException(status_code=404, detail="Survey not found")
    return survey


@router.post("/tasks/{task_id}/runs/{run_id}/survey/generate")
def generate_survey(task_id: str, run_id: str, request: SurveyGenerateRequest, db: Session = Depends(get_db)):
    try:
        return SurveyService(db).generate(task_id, run_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except Exception as exc:  # noqa: BLE001 - keep survey failures isolated from the main workflow.
        status_code, payload = survey_error_response(exc)
        raise HTTPException(status_code=status_code, detail=payload) from exc


@router.post("/tasks/{task_id}/runs/{run_id}/survey/demo-phone")
def create_phone_demo_survey(task_id: str, run_id: str, db: Session = Depends(get_db)):
    try:
        return SurveyService(db).create_phone_demo(task_id, run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task or run not found") from exc
    except Exception as exc:  # noqa: BLE001
        status_code, payload = survey_error_response(exc)
        raise HTTPException(status_code=status_code, detail=payload) from exc


@router.post("/tasks/{task_id}/runs/{run_id}/survey/responses/upload-any")
async def upload_ad_hoc_survey_responses(task_id: str, run_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        raw_content = await file.read()
        return SurveyService(db).upload_ad_hoc_and_analyze(task_id, run_id, file.filename or "responses", raw_content)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task or run not found") from exc
    except Exception as exc:  # noqa: BLE001
        status_code, payload = survey_error_response(exc)
        raise HTTPException(status_code=status_code, detail=payload) from exc


@router.post("/surveys/generate-from-topic")
def generate_survey_from_topic(request: SurveyTopicGenerateRequest, db: Session = Depends(get_db)):
    try:
        return SurveyService(db).generate_from_topic(request)
    except Exception as exc:  # noqa: BLE001
        status_code, payload = survey_error_response(exc)
        raise HTTPException(status_code=status_code, detail=payload) from exc


@router.patch("/surveys/{survey_id}")
def update_survey(survey_id: str, request: SurveyUpdateRequest, db: Session = Depends(get_db)):
    try:
        return SurveyService(db).update_survey(survey_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Survey not found") from exc
    except Exception as exc:  # noqa: BLE001
        status_code, payload = survey_error_response(exc)
        raise HTTPException(status_code=status_code, detail=payload) from exc


@router.post("/surveys/{survey_id}/questions")
def add_survey_question(survey_id: str, request: SurveyAddQuestionRequest, db: Session = Depends(get_db)):
    try:
        return SurveyService(db).add_question(survey_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Survey not found") from exc
    except Exception as exc:  # noqa: BLE001
        status_code, payload = survey_error_response(exc)
        raise HTTPException(status_code=status_code, detail=payload) from exc


@router.delete("/surveys/{survey_id}/questions/{question_id}")
def delete_survey_question(survey_id: str, question_id: str, db: Session = Depends(get_db)):
    try:
        return SurveyService(db).delete_question(survey_id, question_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Survey or question not found") from exc
    except Exception as exc:  # noqa: BLE001
        status_code, payload = survey_error_response(exc)
        raise HTTPException(status_code=status_code, detail=payload) from exc


@router.post("/surveys/{survey_id}/questions/reorder")
def reorder_survey_questions(survey_id: str, request: SurveyReorderRequest, db: Session = Depends(get_db)):
    try:
        return SurveyService(db).reorder_questions(survey_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Survey not found") from exc
    except Exception as exc:  # noqa: BLE001
        status_code, payload = survey_error_response(exc)
        raise HTTPException(status_code=status_code, detail=payload) from exc


@router.post("/surveys/{survey_id}/revise")
def revise_survey(survey_id: str, request: SurveyReviseRequest, db: Session = Depends(get_db)):
    try:
        return SurveyService(db).revise(survey_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Survey not found") from exc
    except Exception as exc:  # noqa: BLE001
        status_code, payload = survey_error_response(exc)
        raise HTTPException(status_code=status_code, detail=payload) from exc


@router.get("/surveys/{survey_id}")
def get_survey(survey_id: str, db: Session = Depends(get_db)):
    try:
        return SurveyService(db).get_survey(survey_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Survey not found") from exc


@router.get("/surveys/{survey_id}/export.csv")
def export_survey_csv(survey_id: str, db: Session = Depends(get_db)):
    try:
        csv_content = SurveyService(db).export_csv(survey_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Survey not found") from exc
    return Response(
        content="\ufeff" + csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{survey_id}.csv"'},
    )


@router.get("/surveys/{survey_id}/response-template.csv")
def export_survey_response_csv(survey_id: str, db: Session = Depends(get_db)):
    try:
        csv_content = SurveyService(db).export_response_csv(survey_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Survey not found") from exc
    return Response(
        content="\ufeff" + csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{survey_id}_response_template.csv"'},
    )


@router.get("/surveys/{survey_id}/sample-responses.csv")
def export_sample_responses_csv(survey_id: str, db: Session = Depends(get_db)):
    try:
        csv_content = SurveyService(db).export_demo_response_csv(survey_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Survey not found") from exc
    return Response(
        content="\ufeff" + csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{survey_id}_sample_responses.csv"'},
    )


@router.post("/surveys/{survey_id}/responses/upload")
async def upload_survey_responses(survey_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        raw_content = await file.read()
        return SurveyService(db).upload_and_analyze(survey_id, file.filename or "responses", raw_content)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Survey not found") from exc
    except Exception as exc:  # noqa: BLE001
        status_code, payload = survey_error_response(exc)
        raise HTTPException(status_code=status_code, detail=payload) from exc


@router.get("/surveys/{survey_id}/analysis")
def get_survey_analysis(survey_id: str, db: Session = Depends(get_db)):
    try:
        return SurveyService(db).latest_analysis(survey_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Survey analysis not found") from exc
