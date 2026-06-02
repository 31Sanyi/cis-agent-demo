from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.agents.runner import default_dag
from app.agents.runner_factory import create_workflow_runner
from app.database import get_db
from app.schemas import CreateTaskRequest
from app.services.evidence_service import EvidenceService
from app.services.llm_client import LlmClient
from app.services.report_service import ReportService
from app.services.task_run_service import TaskRunService
from app.services.task_service import TaskService
from app.services.trace_service import TraceService
from app.services.web_search_client import WebSearchClient

router = APIRouter(prefix="/api")


@router.get("/llm/status")
def llm_status():
    return LlmClient().status()


@router.post("/llm/test")
def test_llm_connection():
    return LlmClient().test_connection()


@router.get("/collector/status")
def collector_status():
    return WebSearchClient().status()


@router.get("/search/status")
def search_status():
    return WebSearchClient().status()


@router.post("/search/test")
def test_search_connection(payload: dict = Body(default_factory=dict)):
    query = payload.get("query") or "飞书 B2B SaaS 功能 定价 官网"
    return WebSearchClient().test_connection(str(query))


@router.post("/tasks")
def create_task(request: CreateTaskRequest, db: Session = Depends(get_db)):
    return TaskService(db).create_task(request)


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    return TaskService(db).list_tasks()


@router.get("/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    try:
        return TaskService(db).get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


@router.post("/tasks/{task_id}/run")
def run_task(
    task_id: str,
    demo_mode: str = Query("normal", pattern="^(normal|qa_missing_evidence|qa_invalid_extraction|qa_bad_report)$"),
    auto_rework: bool = Query(False),
    writer_mode: str = Query("mock", pattern="^(mock|llm)$"),
    collector_mode: str = Query("mock", pattern="^(mock|web)$"),
    analyst_mode: str = Query("evidence", pattern="^(mock|evidence|llm)$"),
    workflow_engine: str | None = Query(None, pattern="^(custom|langgraph)$"),
    content_mode: str | None = Query(None),
    db: Session = Depends(get_db),
):
    try:
        runner, engine = create_workflow_runner(db, workflow_engine)
        if engine == "langgraph":
            return runner.run(
                task_id,
                demo_mode=demo_mode,
                auto_rework=auto_rework,
                writer_mode=writer_mode,
                collector_mode=collector_mode,
                analyst_mode=analyst_mode,
                workflow_engine_requested=workflow_engine or "env/default",
                content_mode=content_mode,
            )
        run_service = TaskRunService(db)
        task_run = run_service.create_run(
            task_id=task_id,
            workflow_engine="custom",
            collector_mode=collector_mode,
            analyst_mode=analyst_mode,
            writer_mode=writer_mode,
            content_mode=content_mode,
            demo_mode=demo_mode,
            auto_rework=auto_rework,
        )
        result = runner.run(
            task_id,
            demo_mode=demo_mode,
            auto_rework=auto_rework,
            writer_mode=writer_mode,
            collector_mode=collector_mode,
            analyst_mode=analyst_mode,
            run_id=task_run.run_id,
        )
        result["workflow_summary"] = {
            "workflow_engine_requested": workflow_engine or "env/default",
            "workflow_engine_used": "custom",
            "workflow_role": "legacy_fallback",
            "primary_workflow_kind": "competitive_analysis_langgraph",
            "follow_up_workflow_kind": "survey_questionnaire_sidecar",
            "survey_integration_mode": "follow_up_sidecar",
            "workflow_data_source": "execution_backed_summary",
            "runner_capability_notes": [
                "Custom Runner is a limited legacy fallback path.",
                "It executes Planner -> Collector -> Analyst -> ReportWriter -> Qa -> FinalReport.",
                "Questionnaire and survey work are follow-up sidecar flows, not part of this runner path.",
            ],
            "intent_classification": result["plan"].intent_classification if result.get("plan") else None,
            "ambiguity_level": result["plan"].ambiguity_level if result.get("plan") else None,
            "scope_type": result["plan"].scope_type if result.get("plan") else None,
            "scope_size": result["plan"].scope_size if result.get("plan") else None,
            "survey_needed": result["plan"].survey_needed if result.get("plan") else False,
            "survey_recommended": result["plan"].survey_recommended if result.get("plan") else False,
            "selected_dimensions": result["plan"].selected_dimensions if result.get("plan") else [],
            "recommended_next_constraints": result["plan"].recommended_next_constraints if result.get("plan") else [],
            "clarification_targets": result["plan"].clarification_targets if result.get("plan") else [],
            "candidate_competitors": [item.model_dump(mode="json") for item in result["plan"].candidate_competitors] if result.get("plan") else [],
            "planning_stages": [item.model_dump(mode="json") for item in result["plan"].planning_stages] if result.get("plan") else [],
            "domain_pack": result["plan"].domain_pack.model_dump(mode="json") if result.get("plan") and result["plan"].domain_pack else None,
            "node_sequence": ["planner", "collector", "analyst", "report_writer", "qa"] + (["final_report"] if result.get("report") else []),
            "conditional_routes_taken": [],
            "rework_count": result["qa_result"].rework_count if result.get("qa_result") else 0,
            "final_status": result["qa_result"].status if result.get("qa_result") else "failed",
        }
        result["workflow_summary"]["core"] = {
            "workflow_engine_requested": result["workflow_summary"]["workflow_engine_requested"],
            "workflow_engine_used": result["workflow_summary"]["workflow_engine_used"],
            "workflow_role": result["workflow_summary"]["workflow_role"],
            "intent_classification": result["workflow_summary"]["intent_classification"],
            "ambiguity_level": result["workflow_summary"]["ambiguity_level"],
            "scope_type": result["workflow_summary"]["scope_type"],
            "scope_size": result["workflow_summary"]["scope_size"],
            "selected_dimensions": result["workflow_summary"]["selected_dimensions"],
            "recommended_next_constraints": result["workflow_summary"]["recommended_next_constraints"],
            "clarification_targets": result["workflow_summary"]["clarification_targets"],
            "candidate_competitors": result["workflow_summary"]["candidate_competitors"],
            "planning_stages": result["workflow_summary"]["planning_stages"],
            "domain_pack": result["workflow_summary"]["domain_pack"],
            "node_sequence": result["workflow_summary"]["node_sequence"],
            "conditional_routes_taken": result["workflow_summary"]["conditional_routes_taken"],
            "rework_count": result["workflow_summary"]["rework_count"],
            "final_status": result["workflow_summary"]["final_status"],
        }
        result["workflow_summary"]["extensions"] = {
            "primary_workflow_kind": result["workflow_summary"]["primary_workflow_kind"],
            "follow_up_workflow_kind": result["workflow_summary"]["follow_up_workflow_kind"],
            "survey": {
                "survey_needed": result["workflow_summary"]["survey_needed"],
                "survey_recommended": result["workflow_summary"].get("survey_recommended", False),
                "survey_objective": result["plan"].survey_objective if result.get("plan") else None,
                "survey_inputs": result["plan"].survey_inputs.model_dump(mode="json") if result.get("plan") and result["plan"].survey_inputs else None,
                "survey_guidance": result["plan"].downstream_guidance.survey if result.get("plan") and result["plan"].downstream_guidance else [],
            },
            "questionnaire_follow_up": result["plan"].questionnaire_follow_up.model_dump(mode="json")
            if result.get("plan") and result["plan"].questionnaire_follow_up
            else None,
        }
        result["workflow_summary"]["diagnostics"] = {
            "workflow_data_source": result["workflow_summary"]["workflow_data_source"],
            "runner_capability_notes": result["workflow_summary"]["runner_capability_notes"],
        }
        final_status = result["workflow_summary"]["final_status"]
        finished_run = run_service.finish_run(
            task_run.run_id,
            status="completed" if final_status in {"passed", "completed"} else str(final_status),
            final_status=final_status,
            elapsed_time_ms=None,
        )
        result["run"] = finished_run
        result["run_id"] = finished_run.run_id
        result["workflow_summary"]["run_id"] = finished_run.run_id
        result["workflow_summary"]["run_isolation_strategy"] = "task_run_bound_custom_fallback"
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


@router.get("/tasks/{task_id}/dag")
def get_dag(task_id: str, db: Session = Depends(get_db)):
    try:
        task = TaskService(db).get_task(task_id)
        return default_dag(task.status)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


@router.get("/tasks/{task_id}/traces")
def get_traces(task_id: str, db: Session = Depends(get_db)):
    run_id = _latest_run_id_or_none(task_id, db)
    return TraceService(db).list_for_task(task_id, run_id=run_id) if run_id else TraceService(db).list_for_task(task_id)


@router.get("/tasks/{task_id}/evidence")
def get_evidence(task_id: str, db: Session = Depends(get_db)):
    run_id = _latest_run_id_or_none(task_id, db)
    return EvidenceService(db).list_for_task(task_id, run_id=run_id) if run_id else EvidenceService(db).list_for_task(task_id)


@router.get("/tasks/{task_id}/qa")
def get_qa(task_id: str, db: Session = Depends(get_db)):
    try:
        run_id = _latest_run_id_or_none(task_id, db)
        return ReportService(db).qa_for_task_run(task_id, run_id) if run_id else ReportService(db).latest_qa(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="QA result not found") from exc


@router.get("/tasks/{task_id}/report")
def get_task_report(task_id: str, db: Session = Depends(get_db)):
    try:
        run_id = _latest_run_id_or_none(task_id, db)
        return ReportService(db).get_for_task_run(task_id, run_id) if run_id else ReportService(db).get_latest_for_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc


@router.get("/reports/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)):
    try:
        return ReportService(db).get_report(report_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc


@router.get("/tasks/{task_id}/runs")
def list_task_runs(task_id: str, db: Session = Depends(get_db)):
    return TaskRunService(db).list_for_task(task_id)


@router.get("/tasks/{task_id}/runs/latest")
def get_latest_task_run(task_id: str, db: Session = Depends(get_db)):
    try:
        return TaskRunService(db).latest_for_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task run not found") from exc


@router.get("/tasks/{task_id}/runs/{run_id}")
def get_task_run(task_id: str, run_id: str, db: Session = Depends(get_db)):
    try:
        return TaskRunService(db).get_run(task_id, run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task run not found") from exc


@router.get("/tasks/{task_id}/runs/{run_id}/evidence")
def get_task_run_evidence(task_id: str, run_id: str, db: Session = Depends(get_db)):
    return EvidenceService(db).list_for_task(task_id, run_id=run_id)


@router.get("/tasks/{task_id}/runs/{run_id}/report")
def get_task_run_report(task_id: str, run_id: str, db: Session = Depends(get_db)):
    try:
        return ReportService(db).get_for_task_run(task_id, run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc


@router.get("/tasks/{task_id}/runs/{run_id}/qa")
def get_task_run_qa(task_id: str, run_id: str, db: Session = Depends(get_db)):
    try:
        return ReportService(db).qa_for_task_run(task_id, run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="QA result not found") from exc


@router.get("/tasks/{task_id}/runs/{run_id}/traces")
def get_task_run_traces(task_id: str, run_id: str, db: Session = Depends(get_db)):
    return TraceService(db).list_for_task(task_id, run_id=run_id)


def _latest_run_id_or_none(task_id: str, db: Session) -> str | None:
    try:
        return TaskRunService(db).latest_for_task(task_id).run_id
    except KeyError:
        return None
