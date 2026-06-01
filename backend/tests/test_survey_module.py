import json

from app.schemas.survey import Survey, SurveyAddQuestionRequest, SurveyQuestionCreate, SurveyReorderRequest, SurveyReviseRequest, SurveyTopicGenerateRequest, SurveyUpdateRequest
from app.database import Base
from app.db_models import TaskRecord, TaskRunRecord
from app.schemas import Claim, QaResult, Report
from app.services.survey_demo_data import PHONE_DEMO_RESPONSE_CSV, PHONE_DEMO_SURVEY_PAYLOAD, build_phone_demo_response_csv_for_survey
from app.services.evidence_service import EvidenceService
from app.services.report_service import ReportService
from app.services.survey_llm_client import SurveyLLMConfigurationError
from app.services.survey_service import SurveyService
from app.utils.csv_exporter import export_survey_template_csv
from app.utils.csv_parser import SurveyCsvValidationError, infer_survey_from_csv, parse_survey_response_csv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _survey() -> Survey:
    return Survey(
        survey_id="survey_test",
        task_id="task_test",
        run_id="run_test",
        title="竞品验证问卷",
        description="验证用户侧问题",
        target_respondents="目标用户",
        research_goal="验证关键结论",
        questions=[
            {
                "question_id": "Q1",
                "field_name": "seat_lock_experience",
                "question_text": "你是否遇到过锁座问题？",
                "question_type": "single_choice",
                "options": ["经常", "偶尔", "从未"],
                "required": True,
                "analysis_goal": "验证锁座问题感知",
                "related_claim_id": "claim_001",
                "reason": "判断用户是否真实感知到问题",
                "order": 1,
            },
            {
                "question_id": "Q2",
                "field_name": "feature_importance",
                "question_text": "你关注哪些功能？",
                "question_type": "multiple_choice",
                "options": ["价格", "体验", "服务"],
                "required": False,
                "analysis_goal": "验证功能偏好",
                "related_claim_id": "claim_002",
                "reason": "判断差异化功能是否被用户重视",
                "order": 2,
            },
            {
                "question_id": "Q3",
                "field_name": "satisfaction_score",
                "question_text": "满意度评分",
                "question_type": "rating",
                "options": ["1", "2", "3", "4", "5"],
                "required": True,
                "analysis_goal": "验证满意度",
                "related_claim_id": None,
                "reason": "量化用户满意度",
                "order": 3,
            },
            {
                "question_id": "Q4",
                "field_name": "pay_amount",
                "question_text": "最多愿意付费多少？",
                "question_type": "number",
                "options": [],
                "required": False,
                "analysis_goal": "验证付费意愿",
                "related_claim_id": None,
                "reason": "量化付费接受度",
                "order": 4,
            },
            {
                "question_id": "Q5",
                "field_name": "open_feedback",
                "question_text": "还有什么建议？",
                "question_type": "text",
                "options": [],
                "required": False,
                "analysis_goal": "收集开放反馈",
                "related_claim_id": None,
                "reason": "补充结构化问题无法覆盖的信息",
                "order": 5,
            },
        ],
    )


def test_survey_schema_requires_unique_field_names():
    payload = _survey().model_dump()
    payload["questions"][1]["field_name"] = "seat_lock_experience"
    try:
        Survey.model_validate(payload)
    except ValueError as exc:
        assert "field_name" in str(exc)
    else:
        raise AssertionError("Duplicate field_name should fail validation")


def test_export_survey_template_csv_uses_expected_header_and_pipe_options():
    csv_content = export_survey_template_csv(_survey())

    assert csv_content.startswith("question_id,field_name,question_text,question_type,options,required,analysis_goal,related_claim_id")
    assert "经常|偶尔|从未" in csv_content
    assert "claim_001" in csv_content


def test_parse_survey_response_csv_stats_question_types():
    csv_content = """seat_lock_experience,feature_importance,satisfaction_score,pay_amount,open_feedback
经常,价格|体验,5,50,体验不透明
偶尔,服务、体验,3,20,
经常,,4,,
"""
    stats = parse_survey_response_csv(csv_content, _survey())

    assert stats["sample_size"] == 3
    assert stats["valid_count"] == 3
    assert stats["questions"]["Q1"]["distribution"]["经常"]["count"] == 2
    assert stats["questions"]["Q2"]["distribution"]["体验"]["count"] == 2
    assert stats["questions"]["Q3"]["average"] == 4
    assert stats["questions"]["Q4"]["median"] == 35
    assert stats["questions"]["Q5"]["text_samples"] == ["体验不透明"]


def test_parse_survey_response_csv_reports_missing_fields():
    try:
        parse_survey_response_csv("seat_lock_experience\n经常\n", _survey())
    except SurveyCsvValidationError as exc:
        assert "feature_importance" in exc.missing_fields
        assert "satisfaction_score" in exc.missing_fields
    else:
        raise AssertionError("Missing survey CSV fields should fail validation")


def test_infer_survey_from_arbitrary_csv_headers_and_analyze_stats():
    csv_content = """你现在用什么品牌,购买手机最看重什么,续航满意度评分,最高预算,换机原因,开放建议
Apple,电池续航,3,6999,续航更强|拍照更好,电池掉电太快
Huawei,影像拍照,5,5999,AI 功能更实用|拍照更好,价格偏高
Xiaomi,价格,4,3999,价格更合适|续航更强,系统弹窗太多
"""
    survey = infer_survey_from_csv(csv_content, task_id="task_any", run_id="run_any")
    types_by_field = {question.field_name: question.question_type for question in survey.questions}

    assert "你现在用什么品牌" in types_by_field
    assert types_by_field["续航满意度评分"] == "rating"
    assert types_by_field["最高预算"] == "number"
    assert types_by_field["换机原因"] == "multiple_choice"
    assert types_by_field["开放建议"] == "text"

    stats = parse_survey_response_csv(csv_content, survey)
    assert stats["sample_size"] == 3
    assert stats["valid_count"] == 3
    assert stats["questions"]["Q4"]["median"] == 5999
    assert stats["questions"]["Q5"]["distribution"]["拍照更好"]["count"] == 2


def test_phone_demo_csv_can_be_parsed_by_matching_survey():
    survey = Survey(
        survey_id="survey_phone_demo",
        task_id="task_phone",
        run_id="run_phone",
        title="手机问卷",
        description="手机问卷",
        target_respondents="手机用户",
        research_goal="验证手机购买偏好",
        questions=[
            {
                "question_id": "Q1",
                "field_name": "purchase_priority",
                "question_text": "购买因素",
                "question_type": "single_choice",
                "options": ["价格", "影像拍照", "电池续航", "系统流畅度", "品牌生态", "AI 功能"],
                "required": True,
                "analysis_goal": "验证购买因素",
                "reason": "验证购买因素",
                "order": 1,
            },
            {
                "question_id": "Q2",
                "field_name": "current_brand",
                "question_text": "当前品牌",
                "question_type": "single_choice",
                "options": ["Apple", "Huawei", "Xiaomi", "OPPO", "vivo", "Samsung", "其他"],
                "required": True,
                "analysis_goal": "验证品牌结构",
                "reason": "验证品牌结构",
                "order": 2,
            },
            {
                "question_id": "Q3",
                "field_name": "battery_satisfaction",
                "question_text": "续航满意度",
                "question_type": "rating",
                "options": ["1", "2", "3", "4", "5"],
                "required": True,
                "analysis_goal": "验证续航满意度",
                "reason": "验证续航满意度",
                "order": 3,
            },
            {
                "question_id": "Q4",
                "field_name": "camera_importance",
                "question_text": "影像重要性",
                "question_type": "rating",
                "options": ["1", "2", "3", "4", "5"],
                "required": True,
                "analysis_goal": "验证影像重要性",
                "reason": "验证影像重要性",
                "order": 4,
            },
            {
                "question_id": "Q5",
                "field_name": "switching_reason",
                "question_text": "切换原因",
                "question_type": "multiple_choice",
                "options": ["价格更合适", "续航更强", "拍照更好", "系统更流畅", "AI 功能更实用", "售后服务更好"],
                "required": True,
                "analysis_goal": "验证切换原因",
                "reason": "验证切换原因",
                "order": 5,
            },
            {
                "question_id": "Q6",
                "field_name": "max_budget",
                "question_text": "预算",
                "question_type": "number",
                "options": [],
                "required": True,
                "analysis_goal": "验证预算",
                "reason": "验证预算",
                "order": 6,
            },
            {
                "question_id": "Q7",
                "field_name": "ai_feature_interest",
                "question_text": "AI 兴趣",
                "question_type": "single_choice",
                "options": ["非常感兴趣", "比较感兴趣", "一般", "不太感兴趣", "完全不感兴趣"],
                "required": True,
                "analysis_goal": "验证 AI 兴趣",
                "reason": "验证 AI 兴趣",
                "order": 7,
            },
            {
                "question_id": "Q8",
                "field_name": "open_feedback",
                "question_text": "开放反馈",
                "question_type": "text",
                "options": [],
                "required": False,
                "analysis_goal": "收集开放反馈",
                "reason": "收集开放反馈",
                "order": 8,
            },
        ],
    )
    stats = parse_survey_response_csv(PHONE_DEMO_RESPONSE_CSV, survey)

    assert stats["sample_size"] == 30
    assert stats["valid_count"] == 30
    assert stats["questions"]["Q6"]["median"] > 4000


def test_phone_demo_revise_falls_back_without_survey_llm_key():
    class MissingKeyQuestionnaireAgent:
        def revise_survey(self, survey_json, revision_request, report_context):
            raise SurveyLLMConfigurationError("SURVEY_LLM_API_KEY is not configured")

    class MissingKeyAnalysisAgent:
        def analyze(self, survey_json, survey_stats_json, report_context):
            raise SurveyLLMConfigurationError("SURVEY_LLM_API_KEY is not configured")

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        service = SurveyService(session, questionnaire_agent=MissingKeyQuestionnaireAgent(), analysis_agent=MissingKeyAnalysisAgent())
        survey = service._survey_from_llm_payload(
            "task_phone",
            "run_phone",
            PHONE_DEMO_SURVEY_PAYLOAD,
            [],
            status="analyzed",
            version=1,
        )
        saved = service.save_survey(survey)
        result = service.revise(
            saved.survey_id,
            request=SurveyReviseRequest(revision_request="压缩到 5 题以内，并增加付费意愿的问题"),
        )

        field_names = [question.field_name for question in result.survey.questions]
        assert result.survey.version == 2
        assert result.survey.status == "revised"
        assert len(result.survey.questions) <= 5
        assert "premium_willingness" in field_names
        assert result.revision_summary
        sample_csv = build_phone_demo_response_csv_for_survey(result.survey)
        assert "premium_willingness" in sample_csv.splitlines()[0]
        stats = parse_survey_response_csv(sample_csv, result.survey)
        assert stats["sample_size"] == 30
        assert stats["invalid_count"] == 0
        exported_sample_csv = service.export_demo_response_csv(saved.survey_id)
        assert "premium_willingness" in exported_sample_csv.splitlines()[0]
        assert len(exported_sample_csv.splitlines()) == 31
        try:
            service.latest_analysis(saved.survey_id)
        except KeyError:
            pass
        else:
            raise AssertionError("Revised surveys should not expose stale analysis")
        upload_result = service.upload_and_analyze(saved.survey_id, "sample.csv", exported_sample_csv)
        assert upload_result.valid_count == 30
        assert upload_result.analysis.key_findings
        assert upload_result.analysis.survey_evidence["confidence"] > 0
        old_csv_upload_result = service.upload_and_analyze(saved.survey_id, "old_sample.csv", PHONE_DEMO_RESPONSE_CSV)
        assert old_csv_upload_result.valid_count == 30
        assert any(
            item.get("field_name") == "premium_willingness"
            for item in old_csv_upload_result.analysis.question_level_analysis
        )
    finally:
        session.close()


def test_upload_mismatched_csv_becomes_ad_hoc_survey_with_generic_fallback():
    class MissingKeyAnalysisAgent:
        def analyze(self, survey_json, survey_stats_json, report_context):
            raise SurveyLLMConfigurationError("SURVEY_LLM_API_KEY is not configured")

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        session.add(
            TaskRecord(
                task_id="task_any",
                product_name="NovaPhone Pro",
                competitors_json=json.dumps(["iPhone 16"]),
                region="China",
                industry="Smartphone",
            )
        )
        session.commit()
        service = SurveyService(session, analysis_agent=MissingKeyAnalysisAgent())
        generated_survey = service.save_survey(_survey().model_copy(update={"task_id": "task_any", "run_id": "run_any"}))
        csv_content = """品牌,购买因素,预算,开放建议
Apple,续航,6999,电池掉电太快
Huawei,影像,5999,价格偏高
Xiaomi,价格,3999,系统弹窗太多
"""

        result = service.upload_and_analyze(generated_survey.survey_id, "custom.csv", csv_content)

        assert result.survey is not None
        assert result.survey.survey_id != generated_survey.survey_id
        assert result.survey.status == "analyzed"
        assert [question.field_name for question in result.survey.questions] == ["品牌", "购买因素", "预算", "开放建议"]
        assert result.valid_count == 3
        assert result.analysis.survey_evidence["metadata"]["analysis_mode"] == "ad_hoc_csv"
        assert result.analysis.question_level_analysis
    finally:
        session.close()


def test_task_level_survey_flow_uses_planner_inputs_and_creates_survey_evidence():
    class MissingKeyQuestionnaireAgent:
        def generate_survey(self, context):
            raise SurveyLLMConfigurationError("SURVEY_LLM_API_KEY is not configured")

        def revise_survey(self, survey_json, revision_request, report_context):
            raise SurveyLLMConfigurationError("SURVEY_LLM_API_KEY is not configured")

    class MissingKeyAnalysisAgent:
        def analyze(self, survey_json, survey_stats_json, report_context):
            raise SurveyLLMConfigurationError("SURVEY_LLM_API_KEY is not configured")

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        session.add(
            TaskRecord(
                task_id="task_planner",
                product_name="NovaPhone Pro",
                competitors_json=json.dumps(["iPhone 16", "Huawei Mate"]),
                region="China",
                industry="Smartphone",
            )
        )
        session.commit()
        service = SurveyService(
            session,
            questionnaire_agent=MissingKeyQuestionnaireAgent(),
            analysis_agent=MissingKeyAnalysisAgent(),
        )

        context = service.planner_context_for_task("task_planner")
        assert context["planner_context"]["survey_needed"] is True
        assert context["planner_context"]["survey_inputs"]["question_themes"]

        survey = service.generate_for_task("task_planner")
        assert survey.metadata["source"] == "planner_output"
        assert len(survey.questions) == 10
        assert any(question.question_type == "rating" for question in survey.questions)
        assert any(question.question_type == "text" for question in survey.questions)

        template = service.export_response_csv_for_task("task_planner")
        headers = template.splitlines()[0].split(",")
        rows = [
            ["r1"] + ["价格" if index != 4 else "4" for index in range(len(headers) - 1)],
            ["r2"] + ["核心功能" if index != 4 else "5" for index in range(len(headers) - 1)],
            ["r3"] + ["体验不稳定" if index != 4 else "3" for index in range(len(headers) - 1)],
        ]
        csv_content = ",".join(headers) + "\n" + "\n".join(",".join(row) for row in rows) + "\n"
        result = service.import_csv_for_task("task_planner", "responses.csv", csv_content)

        assert result.sample_size == 3
        assert result.question_summaries
        assert result.hypothesis_findings
        assert result.survey_evidence
        assert result.evidence
        assert result.evidence["source_type"] == "survey"
        assert result.evidence["local_ref"] == f"survey://{survey.survey_id}"
        saved_evidence = EvidenceService(session).list_for_task("task_planner", run_id=survey.run_id)
        assert any(item.source_type == "survey" for item in saved_evidence)
    finally:
        session.close()


def test_planner_context_for_task_prefers_latest_report_planner_snapshot():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        session.add(
            TaskRecord(
                task_id="task_report_snapshot",
                product_name="NovaPhone Pro",
                competitors_json=json.dumps(["iPhone 16", "Huawei Mate"]),
                region="China",
                industry="Smartphone",
            )
        )
        session.add(
            TaskRunRecord(
                run_id="run_report_snapshot",
                task_id="task_report_snapshot",
                workflow_engine="custom",
                collector_mode="mock",
                analyst_mode="evidence",
                writer_mode="mock",
                content_mode=None,
                demo_mode="normal",
                auto_rework=False,
                status="completed",
                final_status="passed",
            )
        )
        session.commit()
        report = Report(
            task_id="task_report_snapshot",
            markdown="# report",
            json_report={
                "planner": {
                    "intent_classification": "competitive_analysis",
                    "selected_dimensions": ["feature", "pricing"],
                    "survey_needed": True,
                    "survey_recommended": True,
                    "survey_objective": "验证价格敏感度与换机动机",
                    "survey_inputs": {
                        "objective": "验证价格敏感度与换机动机",
                        "respondent_type": "中国智能手机潜在用户",
                        "question_themes": ["预算", "换机原因"],
                        "hypotheses": ["价格敏感用户更容易转向竞品"],
                        "metadata": {"source": "test"},
                    },
                    "writer_guidance": ["强调证据空白"],
                }
            },
            claims=[Claim(claim_id="claim_001", competitor="iPhone 16", text="test", evidence_ids=["ev_1"], category="pricing", confidence=0.8)],
            qa_result=QaResult(task_id="task_report_snapshot", status="passed"),
        )
        ReportService(session).save_report(report, run_id="run_report_snapshot")

        context = SurveyService(session).planner_context_for_task("task_report_snapshot")["planner_context"]

        assert context["survey_needed"] is True
        assert context["survey_recommended"] is True
        assert context["survey_objective"] == "验证价格敏感度与换机动机"
        assert context["survey_inputs"]["respondent_type"] == "中国智能手机潜在用户"
        assert context["survey_inputs"]["question_themes"] == ["预算", "换机原因"]
        assert context["diagnostics"]["source"] == "report_json_planner_snapshot"
    finally:
        session.close()


def test_topic_survey_generation_and_manual_editing_without_llm_key():
    class MissingKeyQuestionnaireAgent:
        def generate_from_topic(self, context):
            raise SurveyLLMConfigurationError("SURVEY_LLM_API_KEY is not configured")

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        service = SurveyService(session, questionnaire_agent=MissingKeyQuestionnaireAgent())
        survey = service.generate_from_topic(
            SurveyTopicGenerateRequest(
                topic="高校学生对 AI 学习工具的使用与付费意愿",
                target_respondents="高校学生",
                research_goal="识别真实使用场景、痛点和付费意愿",
                question_count=8,
            )
        )

        assert survey.task_id == "manual_topic"
        assert survey.run_id == "manual_topic"
        assert survey.metadata["source"] == "topic_generation"
        assert "AI 学习工具" in survey.title
        assert len(survey.questions) == 8

        updated = service.update_survey(
            survey.survey_id,
            SurveyUpdateRequest(
                title="AI 学习工具调研问卷",
                questions=[
                    {
                        "question_id": survey.questions[0].question_id,
                        "question_text": "你使用 AI 学习工具的频率是？",
                        "field_name": "ai_tool_usage_frequency",
                        "question_type": "single_choice",
                        "options": ["每天", "每周数次", "偶尔", "从未"],
                        "analysis_goal": "验证使用频率。",
                    }
                ],
            ),
        )

        assert updated.version == 2
        assert updated.questions[0].field_name == "ai_tool_usage_frequency"
        assert updated.csv_columns[0] == "ai_tool_usage_frequency"
        assert service.export_response_csv(updated.survey_id).splitlines()[0].startswith("respondent_id,ai_tool_usage_frequency")

        added = service.add_question(
            updated.survey_id,
            SurveyAddQuestionRequest(
                question=SurveyQuestionCreate(
                    field_name="paid_plan_interest",
                    question_text="如果效果稳定，你是否愿意为 AI 学习工具付费？",
                    question_type="single_choice",
                    options=["不愿意", "10 元以内/月", "10-30 元/月", "30 元以上/月"],
                    analysis_goal="验证付费意愿。",
                )
            ),
        )
        assert "paid_plan_interest" in added.csv_columns

        question_ids = [question.question_id for question in added.questions]
        reordered = service.reorder_questions(
            added.survey_id,
            SurveyReorderRequest(question_ids=[question_ids[-1], *question_ids[:-1]]),
        )
        assert reordered.questions[0].field_name == "paid_plan_interest"

        deleted = service.delete_question(reordered.survey_id, reordered.questions[0].question_id)
        assert "paid_plan_interest" not in deleted.csv_columns
    finally:
        session.close()
