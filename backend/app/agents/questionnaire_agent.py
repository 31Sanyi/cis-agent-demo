import json
import re
from typing import Any

from app.schemas.survey import SurveyBrief, SurveyReviewResult
from app.services.survey_llm_client import SurveyLLMClient

QUESTIONNAIRE_SYSTEM_PROMPT = """你是竞品分析系统中的 QuestionnaireAgent。
你的任务不是生成通用满意度问卷，而是基于 PlannerAgent 的调研规划、竞品分析报告、关键 claims，以及 PainPointResearchAgent 提取出的产品痛点，生成一份可投放给真实用户的痛点验证型问卷。
问卷必须满足：
1. 优先围绕 pain_points 生成，每个核心 pain point 至少覆盖 1-3 道题；
2. 非背景题必须绑定 maps_to_pain_id；
3. 至少覆盖背景信息、痛点存在性、频率或严重程度、购买/续费/推荐/转向竞品影响、解决方案偏好、开放反馈；
4. 每道题必须包含 field_name、question_type、options、analysis_goal、research_purpose、analysis_method、metric_role、reason；
5. field_name 必须唯一，只能由英文字母、数字、下划线组成，且以字母开头；
6. 不要使用 unrelated 的上下文编造强结论，不要索取敏感隐私信息；
7. 输出必须是合法 JSON，不要输出 Markdown。"""

QUESTIONNAIRE_REVISION_SYSTEM_PROMPT = """你是竞品分析系统中的 QuestionnaireAgent。
你需要根据用户修改意见或系统 review 结果，对已有痛点验证问卷进行返工。保留仍然有价值的问题，修复覆盖不足、问题模糊、field_name 不合法、maps_to_pain_id 缺失等问题。输出必须是合法 JSON。"""

QUESTIONNAIRE_TOPIC_SYSTEM_PROMPT = """你是竞品分析系统中的 QuestionnaireAgent。
你的任务是根据 SurveyBrief 生成一份痛点验证型问卷，而不是通用满意度问卷。请围绕 brief 中的 pain_points、target_respondents、research_goal 和 requirements 组织题目，保证结果可编辑、可 CSV 导出、可统计分析。输出必须是合法 JSON。"""

QUESTIONNAIRE_BRIEF_SYSTEM_PROMPT = """你是问卷调研需求整理助手。你的任务不是直接生成问卷，而是根据前端问答记录整理一份 SurveyBrief。
请提取：研究主题、产品/服务/场景、目标受访者、核心痛点、研究目标、竞品或替代方案、额外要求、建议题量。
如果用户没有明确说痛点，请根据上下文推断 2-5 个待验证痛点，但必须在 metadata 中标记 inferred=true。
输出必须是合法 JSON，不要输出 Markdown。"""

QUESTIONNAIRE_REVIEW_SYSTEM_PROMPT = """你是 Survey Reviewer。请审核一份痛点验证型问卷是否适合展示给用户。
审核标准：
1. 是否覆盖所有核心 pain_points；
2. 每个非背景题是否绑定 maps_to_pain_id；
3. 是否包含筛选/背景题；
4. 是否包含痛点存在性、频率或严重程度问题；
5. 是否包含购买/续费/推荐/转向竞品影响问题；
6. 是否包含解决方案偏好或优先级问题；
7. 是否至少有一个开放反馈题；
8. 是否存在诱导性、重复、模糊或无法统计的问题；
9. 选项是否互斥、完整、可统计；
10. field_name 是否唯一且合法；
11. 是否适合 CSV 后续分析。
输出合法 JSON：passed, score, issues, rewrite_instruction。"""


class QuestionnaireAgent:
    def __init__(self, llm_client: SurveyLLMClient | None = None):
        self.llm_client = llm_client or SurveyLLMClient()

    def generate_survey(self, context: dict[str, Any]) -> dict[str, Any]:
        return self.llm_client.generate_json(
            QUESTIONNAIRE_SYSTEM_PROMPT,
            build_questionnaire_prompt(context),
        ).data

    def generate_from_topic(self, context: dict[str, Any]) -> dict[str, Any]:
        return self.generate_from_brief(context)

    def generate_from_brief(self, brief: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.llm_client.generate_json(
                QUESTIONNAIRE_TOPIC_SYSTEM_PROMPT,
                build_brief_questionnaire_prompt(brief),
            ).data
        except Exception:  # noqa: BLE001
            return self._fallback_survey_from_brief(brief)

    def build_survey_brief_from_qa(self, context: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.llm_client.generate_json(
                QUESTIONNAIRE_BRIEF_SYSTEM_PROMPT,
                build_brief_prompt(context),
            ).data
        except Exception:  # noqa: BLE001
            return self._fallback_brief_from_qa(context)

    def review_survey(self, survey_json: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.llm_client.generate_json(
                QUESTIONNAIRE_REVIEW_SYSTEM_PROMPT,
                build_review_prompt(survey_json, context),
            ).data
        except Exception:  # noqa: BLE001
            return self._fallback_review_survey(survey_json, context)

    def revise_survey(
        self,
        survey_json: dict[str, Any],
        revision_request: str,
        report_context: dict[str, Any],
    ) -> dict[str, Any]:
        return self.llm_client.generate_json(
            QUESTIONNAIRE_REVISION_SYSTEM_PROMPT,
            build_revision_prompt(survey_json, revision_request, report_context),
        ).data

    def revise_survey_by_review(
        self,
        survey_json: dict[str, Any],
        review_result: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        rewrite_instruction = str(review_result.get("rewrite_instruction") or "").strip()
        if rewrite_instruction:
            try:
                return self.llm_client.generate_json(
                    QUESTIONNAIRE_REVISION_SYSTEM_PROMPT,
                    build_revision_prompt(survey_json, rewrite_instruction, context),
                ).data
            except Exception:  # noqa: BLE001
                pass
        return self._fallback_revise_by_review(survey_json, review_result, context)

    def generate_with_self_review(self, context: dict[str, Any], max_review_rounds: int = 3) -> dict[str, Any]:
        draft = self.generate_survey(context)
        return self._run_self_review_loop(draft, context, max_review_rounds=max_review_rounds)

    def generate_from_brief_with_self_review(self, brief: dict[str, Any], max_review_rounds: int = 3) -> dict[str, Any]:
        draft = self.generate_from_brief(brief)
        return self._run_self_review_loop(draft, brief, max_review_rounds=max_review_rounds)

    def _run_self_review_loop(self, draft: dict[str, Any], context: dict[str, Any], *, max_review_rounds: int) -> dict[str, Any]:
        best_draft = draft
        for round_index in range(max_review_rounds):
            review = self.review_survey(draft, context)
            draft.setdefault("metadata", {})["review_result"] = review
            if review.get("passed"):
                draft["metadata"]["self_review_passed"] = True
                draft["metadata"]["self_review_rounds"] = round_index + 1
                return draft
            best_draft = draft
            draft = self.revise_survey_by_review(draft, review, context)
        best_draft.setdefault("metadata", {})["review_result"] = self.review_survey(best_draft, context)
        best_draft["metadata"]["self_review_passed"] = False
        best_draft["metadata"]["self_review_rounds"] = max_review_rounds
        return best_draft

    def _fallback_brief_from_qa(self, context: dict[str, Any]) -> dict[str, Any]:
        qa_messages = [item for item in context.get("qa_messages") or [] if isinstance(item, dict)]
        user_answers = [str(item.get("content") or "").strip() for item in qa_messages if item.get("role") == "user" and str(item.get("content") or "").strip()]
        topic = user_answers[0] if len(user_answers) > 0 else ""
        pain_answer = user_answers[1] if len(user_answers) > 1 else ""
        respondents = user_answers[2] if len(user_answers) > 2 else ""
        goal = user_answers[3] if len(user_answers) > 3 else ""
        requirements = user_answers[4] if len(user_answers) > 4 else ""
        pain_points = _split_pain_points(pain_answer)
        inferred = False
        if not pain_points:
            pain_points = _infer_pain_points_from_topic(topic, goal)
            inferred = True
        competitors = _extract_competitors(topic + "\n" + goal + "\n" + requirements)
        return SurveyBrief(
            research_topic=topic or "用户需求验证",
            product_or_category=topic or "待调研产品/场景",
            target_respondents=respondents or "相关目标用户",
            research_goal=goal or f"围绕“{topic or '该主题'}”收集可统计的用户反馈。",
            pain_points=pain_points[:5],
            competitors=competitors,
            requirements=requirements,
            question_count=int(context.get("question_count") or 10),
            metadata={
                "source": "qa_fallback",
                "inferred": inferred,
                "qa_turns": len(qa_messages),
            },
        ).model_dump(mode="json")

    def _fallback_survey_from_brief(self, brief: dict[str, Any]) -> dict[str, Any]:
        normalized_brief = SurveyBrief.model_validate(brief)
        pain_points = normalized_brief.pain_points or _infer_pain_points_from_topic(
            normalized_brief.research_topic or normalized_brief.product_or_category,
            normalized_brief.research_goal,
        )
        question_limit = normalized_brief.question_count
        pain_payloads = [
            {
                "pain_id": f"P{index}",
                "pain_point": pain_point,
                "source_from_report": "brief_generation",
                "confidence": 0.55,
                "why_need_survey": "需要通过问卷确认该痛点是否真实、普遍并影响决策。",
                "research_questions": [
                    "该痛点是否存在？",
                    "该痛点有多严重？",
                    "它是否会影响选择或转向竞品？",
                ],
                "metadata": {"source": "brief_generation"},
            }
            for index, pain_point in enumerate(pain_points[:5], start=1)
        ]
        questions: list[dict[str, Any]] = [
            {
                "question_id": "Q1",
                "field_name": "respondent_segment",
                "question_text": "你更接近以下哪类受访者？",
                "question_type": "single_choice",
                "options": ["当前用户", "潜在用户", "竞品用户", "最近评估过该类产品的人", "其他"],
                "required": True,
                "analysis_goal": "识别样本结构并支持后续分层分析。",
                "related_claim_id": None,
                "maps_to_pain_id": None,
                "research_purpose": "背景分层",
                "analysis_method": "按受访者类型统计各痛点表现差异。",
                "metric_role": "background",
                "theme": "背景信息",
                "hypothesis": None,
                "reason": "背景题用于解释不同用户群对痛点的反馈差异。",
            }
        ]
        for pain in pain_payloads:
            if len(questions) >= question_limit - 1:
                break
            pain_id = pain["pain_id"]
            prefix = _slugify(pain["pain_point"])[:24] or pain_id.lower()
            questions.extend(
                [
                    {
                        "question_id": f"Q{len(questions) + 1}",
                        "field_name": f"{prefix}_existence",
                        "question_text": f"在使用或评估相关产品时，你是否遇到过“{pain['pain_point']}”这类问题？",
                        "question_type": "single_choice",
                        "options": ["经常遇到", "偶尔遇到", "很少遇到", "从未遇到"],
                        "required": True,
                        "analysis_goal": "验证痛点是否真实存在。",
                        "related_claim_id": None,
                        "maps_to_pain_id": pain_id,
                        "research_purpose": "痛点存在性验证",
                        "analysis_method": "统计痛点被感知的比例和频率。",
                        "metric_role": "pain_existence",
                        "theme": pain["pain_point"],
                        "hypothesis": pain["pain_point"],
                        "reason": "验证该痛点是否被目标用户真实感知。",
                    },
                    {
                        "question_id": f"Q{len(questions) + 2}",
                        "field_name": f"{prefix}_severity",
                        "question_text": f"如果这个问题出现，它对你的体验或决策影响有多大？",
                        "question_type": "rating",
                        "options": ["1", "2", "3", "4", "5"],
                        "required": True,
                        "analysis_goal": "衡量痛点严重程度。",
                        "related_claim_id": None,
                        "maps_to_pain_id": pain_id,
                        "research_purpose": "痛点严重度量化",
                        "analysis_method": "计算平均分并识别高严重度痛点。",
                        "metric_role": "pain_severity",
                        "theme": pain["pain_point"],
                        "hypothesis": pain["pain_point"],
                        "reason": "量化痛点强度，避免只凭个别样本下结论。",
                    },
                    {
                        "question_id": f"Q{len(questions) + 3}",
                        "field_name": f"{prefix}_switching_risk",
                        "question_text": "如果竞品能更好解决这个问题，你会多大程度考虑转向竞品？",
                        "question_type": "single_choice",
                        "options": ["完全不会", "大概率不会", "会纳入比较", "很可能转向", "已经因此转向过"],
                        "required": True,
                        "analysis_goal": "判断痛点对购买、续费、推荐或转向竞品的影响。",
                        "related_claim_id": None,
                        "maps_to_pain_id": pain_id,
                        "research_purpose": "竞品影响验证",
                        "analysis_method": "统计高切换风险选项占比。",
                        "metric_role": "switching_risk",
                        "theme": pain["pain_point"],
                        "hypothesis": pain["pain_point"],
                        "reason": "验证该痛点是否会转化成真实业务风险。",
                    },
                    {
                        "question_id": f"Q{len(questions) + 4}",
                        "field_name": f"{prefix}_solution_priority",
                        "question_text": "如果要优先解决一个问题，你会把这个问题放在什么优先级？",
                        "question_type": "single_choice",
                        "options": ["最高优先级", "较高优先级", "一般", "较低优先级", "不需要优先处理"],
                        "required": True,
                        "analysis_goal": "确认解决方案优先级。",
                        "related_claim_id": None,
                        "maps_to_pain_id": pain_id,
                        "research_purpose": "解决方案优先级判断",
                        "analysis_method": "统计高优先级反馈比例。",
                        "metric_role": "solution_preference",
                        "theme": pain["pain_point"],
                        "hypothesis": pain["pain_point"],
                        "reason": "帮助判断该痛点是否值得在产品或报告中重点处理。",
                    },
                ]
            )
            if len(questions) >= question_limit - 1:
                break
        questions = questions[: max(question_limit - 1, 1)]
        questions.append(
            {
                "question_id": f"Q{len(questions) + 1}",
                "field_name": "open_feedback",
                "question_text": "还有哪些未覆盖的痛点、场景或建议，希望补充给我们？",
                "question_type": "text",
                "options": [],
                "required": False,
                "analysis_goal": "收集结构化题目之外的重要补充信息。",
                "related_claim_id": None,
                "maps_to_pain_id": pain_payloads[0]["pain_id"] if pain_payloads else None,
                "research_purpose": "开放反馈补充",
                "analysis_method": "提取高频主题作为定性补充，不做过度推断。",
                "metric_role": "open_feedback",
                "theme": "开放反馈",
                "hypothesis": None,
                "reason": "保留一个开放反馈入口，避免遗漏新痛点。",
            }
        )
        questions = _renumber_questions(questions)
        return {
            "survey_title": f"{normalized_brief.product_or_category or normalized_brief.research_topic} 痛点验证问卷",
            "survey_description": "基于问答式调研 brief 生成，用于验证核心痛点、决策影响与改进优先级。",
            "target_respondents": normalized_brief.target_respondents or "相关目标用户",
            "research_goal": normalized_brief.research_goal or f"验证 {normalized_brief.research_topic or normalized_brief.product_or_category} 的关键用户痛点。",
            "pain_points": pain_payloads,
            "questions": questions,
            "expected_analysis_dimensions": ["背景分层", "痛点存在性", "严重程度", "竞品影响", "解决方案优先级"],
            "csv_columns": [question["field_name"] for question in questions],
            "question_pain_mapping": {
                question["question_id"]: question["maps_to_pain_id"]
                for question in questions
                if question.get("maps_to_pain_id")
            },
            "metadata": {
                "source": "brief_generation",
                "brief": normalized_brief.model_dump(mode="json"),
            },
        }

    def _fallback_review_survey(self, survey_json: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        brief_pain_points = [
            item.get("pain_id") or f"P{index}"
            for index, item in enumerate(survey_json.get("pain_points") or [], start=1)
            if isinstance(item, dict)
        ]
        pain_points = {
            item.get("pain_id") or f"P{index}": str(item.get("pain_point") or "")
            for index, item in enumerate(survey_json.get("pain_points") or [], start=1)
            if isinstance(item, dict)
        }
        questions = list(survey_json.get("questions") or [])
        issues: list[dict[str, Any]] = []
        seen_fields: set[str] = set()
        has_background = False
        has_existence = False
        has_frequency_or_severity = False
        has_switching = False
        has_solution = False
        has_open_feedback = False
        covered_pain_ids: set[str] = set()
        illegal_field_names: list[str] = []
        non_background_without_pain = 0

        for question in questions:
            metric_role = question.get("metric_role")
            pain_id = question.get("maps_to_pain_id")
            field_name = str(question.get("field_name") or "")
            if metric_role == "background":
                has_background = True
            if metric_role == "pain_existence":
                has_existence = True
            if metric_role in {"pain_frequency", "pain_severity"}:
                has_frequency_or_severity = True
            if metric_role in {"switching_risk", "competitor_preference", "willingness_to_pay"}:
                has_switching = True
            if metric_role in {"solution_preference", "pain_priority"}:
                has_solution = True
            if metric_role == "open_feedback" or question.get("question_type") == "text":
                has_open_feedback = True
            if pain_id:
                covered_pain_ids.add(str(pain_id))
            elif metric_role not in {None, "background", "open_feedback"}:
                non_background_without_pain += 1
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", field_name):
                illegal_field_names.append(field_name or str(question.get("question_id") or ""))
            if field_name in seen_fields:
                issues.append(
                    {
                        "severity": "high",
                        "issue": f"field_name 重复：{field_name}",
                        "suggestion": "确保每道题的 field_name 唯一且可用于 CSV 表头。",
                        "related_question_id": question.get("question_id"),
                        "related_pain_id": pain_id,
                    }
                )
            seen_fields.add(field_name)
            if question.get("question_type") in {"single_choice", "multiple_choice", "rating"} and not list(question.get("options") or []):
                issues.append(
                    {
                        "severity": "high",
                        "issue": f"{question.get('question_id')} 缺少可统计选项",
                        "suggestion": "为选择题和评分题补齐互斥、完整、可统计的选项。",
                        "related_question_id": question.get("question_id"),
                        "related_pain_id": pain_id,
                    }
                )

        for pain_id in brief_pain_points:
            if pain_id not in covered_pain_ids:
                issues.append(
                    {
                        "severity": "high",
                        "issue": f"未覆盖核心痛点 {pain_id}",
                        "suggestion": f"至少增加 1-3 道绑定到 {pain_id} 的验证题。",
                        "related_pain_id": pain_id,
                    }
                )
        if not has_background:
            issues.append({"severity": "medium", "issue": "缺少背景/筛选题", "suggestion": "增加至少 1 道背景题用于样本分层。"})
        if not has_existence:
            issues.append({"severity": "high", "issue": "缺少痛点存在性题", "suggestion": "增加 pain_existence 题验证核心痛点是否真实存在。"})
        if not has_frequency_or_severity:
            issues.append({"severity": "medium", "issue": "缺少频率或严重程度题", "suggestion": "增加 pain_frequency 或 pain_severity 题。"})
        if not has_switching:
            issues.append({"severity": "medium", "issue": "缺少竞品影响题", "suggestion": "增加购买/续费/推荐/转向竞品影响题。"})
        if not has_solution:
            issues.append({"severity": "medium", "issue": "缺少解决方案优先级题", "suggestion": "增加 solution_preference 或 pain_priority 题。"})
        if not has_open_feedback:
            issues.append({"severity": "low", "issue": "缺少开放反馈题", "suggestion": "至少增加 1 道开放题补充结构化题目之外的信息。"})
        if illegal_field_names:
            issues.append(
                {
                    "severity": "high",
                    "issue": f"存在不合法 field_name：{', '.join(illegal_field_names[:4])}",
                    "suggestion": "使用英文字母开头，仅保留字母、数字、下划线。",
                }
            )
        if non_background_without_pain:
            issues.append(
                {
                    "severity": "high",
                    "issue": f"{non_background_without_pain} 道非背景题未绑定 maps_to_pain_id",
                    "suggestion": "所有验证题都应绑定到明确的 pain_id。",
                }
            )

        score = 100
        for issue in issues:
            severity = issue["severity"]
            score -= 25 if severity == "high" else 12 if severity == "medium" else 5
        score = max(score, 0)
        review = SurveyReviewResult(
            passed=not any(issue["severity"] == "high" for issue in issues) and score >= 70,
            score=score,
            issues=issues,
            rewrite_instruction="；".join(issue["suggestion"] for issue in issues[:6]),
            metadata={
                "review_mode": "fallback",
                "pain_points": pain_points,
                "question_count": len(questions),
            },
        )
        return review.model_dump(mode="json")

    def _fallback_revise_by_review(self, survey_json: dict[str, Any], review_result: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        payload = json.loads(json.dumps(survey_json, ensure_ascii=False))
        questions = _renumber_questions(list(payload.get("questions") or []))
        pain_points = list(payload.get("pain_points") or [])
        pain_by_id = {
            str(pain.get("pain_id") or f"P{index}"): str(pain.get("pain_point") or "")
            for index, pain in enumerate(pain_points, start=1)
            if isinstance(pain, dict)
        }
        if not any(question.get("metric_role") == "background" for question in questions):
            questions.insert(
                0,
                {
                    "question_id": "Q0",
                    "field_name": "respondent_segment",
                    "question_text": "你更接近以下哪类受访者？",
                    "question_type": "single_choice",
                    "options": ["当前用户", "潜在用户", "竞品用户", "最近评估过该类产品的人", "其他"],
                    "required": True,
                    "analysis_goal": "识别样本结构并支持后续分层分析。",
                    "related_claim_id": None,
                    "maps_to_pain_id": None,
                    "research_purpose": "背景分层",
                    "analysis_method": "按受访者类型统计差异。",
                    "metric_role": "background",
                    "theme": "背景信息",
                    "hypothesis": None,
                    "reason": "补齐 review 要求的背景题。",
                },
            )
        for question in questions:
            field_name = _slugify(question.get("field_name") or question.get("question_text") or question.get("question_id") or "question")
            question["field_name"] = field_name
            metric_role = question.get("metric_role")
            if metric_role not in {None, "background", "open_feedback"} and not question.get("maps_to_pain_id") and pain_by_id:
                question["maps_to_pain_id"] = next(iter(pain_by_id))
            if question.get("question_type") == "rating" and not question.get("options"):
                question["options"] = ["1", "2", "3", "4", "5"]
            if question.get("question_type") in {"single_choice", "multiple_choice"} and not question.get("options"):
                question["options"] = ["选项 A", "选项 B", "其他"]
        for pain_id, pain_text in pain_by_id.items():
            if not any(question.get("maps_to_pain_id") == pain_id for question in questions):
                questions.append(
                    {
                        "question_id": f"Q{len(questions) + 1}",
                        "field_name": f"{pain_id.lower()}_existence",
                        "question_text": f"你是否遇到过“{pain_text}”这类问题？",
                        "question_type": "single_choice",
                        "options": ["经常遇到", "偶尔遇到", "很少遇到", "从未遇到"],
                        "required": True,
                        "analysis_goal": "补齐核心痛点覆盖。",
                        "related_claim_id": None,
                        "maps_to_pain_id": pain_id,
                        "research_purpose": "痛点存在性验证",
                        "analysis_method": "统计感知比例。",
                        "metric_role": "pain_existence",
                        "theme": pain_text,
                        "hypothesis": pain_text,
                        "reason": "根据 review 补齐未覆盖的核心痛点。",
                    }
                )
        if not any(question.get("metric_role") in {"pain_frequency", "pain_severity"} for question in questions) and pain_by_id:
            pain_id, pain_text = next(iter(pain_by_id.items()))
            questions.append(
                {
                    "question_id": f"Q{len(questions) + 1}",
                    "field_name": f"{pain_id.lower()}_severity",
                    "question_text": f"“{pain_text}”对你的体验或决策影响有多大？",
                    "question_type": "rating",
                    "options": ["1", "2", "3", "4", "5"],
                    "required": True,
                    "analysis_goal": "补齐严重程度量化。",
                    "related_claim_id": None,
                    "maps_to_pain_id": pain_id,
                    "research_purpose": "痛点严重度量化",
                    "analysis_method": "计算均值和高分占比。",
                    "metric_role": "pain_severity",
                    "theme": pain_text,
                    "hypothesis": pain_text,
                    "reason": "根据 review 补齐严重程度问题。",
                }
            )
        if not any(question.get("metric_role") in {"switching_risk", "competitor_preference", "willingness_to_pay"} for question in questions) and pain_by_id:
            pain_id, pain_text = next(iter(pain_by_id.items()))
            questions.append(
                {
                    "question_id": f"Q{len(questions) + 1}",
                    "field_name": f"{pain_id.lower()}_switching_risk",
                    "question_text": f"如果竞品能更好解决“{pain_text}”，你会多大程度考虑转向竞品？",
                    "question_type": "single_choice",
                    "options": ["完全不会", "大概率不会", "会纳入比较", "很可能转向", "已经因此转向过"],
                    "required": True,
                    "analysis_goal": "补齐竞品影响验证。",
                    "related_claim_id": None,
                    "maps_to_pain_id": pain_id,
                    "research_purpose": "竞品影响验证",
                    "analysis_method": "统计高切换风险比例。",
                    "metric_role": "switching_risk",
                    "theme": pain_text,
                    "hypothesis": pain_text,
                    "reason": "根据 review 补齐竞品影响问题。",
                }
            )
        if not any(question.get("metric_role") in {"solution_preference", "pain_priority"} for question in questions) and pain_by_id:
            pain_id, pain_text = next(iter(pain_by_id.items()))
            questions.append(
                {
                    "question_id": f"Q{len(questions) + 1}",
                    "field_name": f"{pain_id.lower()}_solution_priority",
                    "question_text": f"你希望多快优先解决“{pain_text}”？",
                    "question_type": "single_choice",
                    "options": ["立即优先解决", "近期优先", "中期考虑", "暂不优先", "无所谓"],
                    "required": True,
                    "analysis_goal": "补齐解决方案优先级验证。",
                    "related_claim_id": None,
                    "maps_to_pain_id": pain_id,
                    "research_purpose": "解决优先级判断",
                    "analysis_method": "统计高优先级比例。",
                    "metric_role": "solution_preference",
                    "theme": pain_text,
                    "hypothesis": pain_text,
                    "reason": "根据 review 补齐解决方案优先级问题。",
                }
            )
        if not any(question.get("metric_role") == "open_feedback" or question.get("question_type") == "text" for question in questions):
            questions.append(
                {
                    "question_id": f"Q{len(questions) + 1}",
                    "field_name": "open_feedback",
                    "question_text": "还有哪些未覆盖的痛点、场景或建议，希望补充给我们？",
                    "question_type": "text",
                    "options": [],
                    "required": False,
                    "analysis_goal": "补充开放反馈。",
                    "related_claim_id": None,
                    "maps_to_pain_id": next(iter(pain_by_id), None),
                    "research_purpose": "开放反馈补充",
                    "analysis_method": "提取高频主题。",
                    "metric_role": "open_feedback",
                    "theme": "开放反馈",
                    "hypothesis": None,
                    "reason": "根据 review 补齐开放题。",
                }
            )
        questions = _dedupe_field_names(_renumber_questions(questions))
        payload["questions"] = questions
        payload["csv_columns"] = [question["field_name"] for question in questions]
        payload["question_pain_mapping"] = {
            question["question_id"]: question["maps_to_pain_id"]
            for question in questions
            if question.get("maps_to_pain_id")
        }
        metadata = dict(payload.get("metadata") or {})
        metadata["review_result"] = review_result
        metadata["revision_source"] = "self_review_fallback"
        payload["metadata"] = metadata
        return payload


def build_questionnaire_prompt(context: dict[str, Any]) -> str:
    return f"""请严格基于以下输入生成问卷：
【产品名称】
{context.get("product_name", "")}
【竞品列表】
{json.dumps(context.get("competitors", []), ensure_ascii=False)}
【行业】
{context.get("industry", "")}
【地区】
{context.get("region", "")}
【竞品分析报告】
{context.get("report_markdown", "")}
【关键结论 Claims】
{json.dumps(context.get("claims_json", []), ensure_ascii=False)}
【PlannerAgent 上下文】
{json.dumps(context.get("planner_context", {}), ensure_ascii=False)}
【产品痛点 pain_points】
{json.dumps(context.get("pain_points", []), ensure_ascii=False)}
【低置信度或需要用户验证的问题】
{json.dumps(context.get("uncertain_findings", []), ensure_ascii=False)}
【用户额外要求】
{context.get("user_requirements", "")}

生成要求：
1. 问卷必须优先围绕 pain_points 生成，不要泛泛覆盖所有竞品分析维度。
2. 每个 core pain point 至少被 1-3 道题覆盖。
3. 背景题可以 maps_to_pain_id=null，所有验证题都必须绑定到一个 pain_id。
4. 每道题必须包含 research_purpose、analysis_method、metric_role。
5. 至少包含背景题、痛点存在性、频率或严重程度、竞品影响、解决方案偏好、开放反馈。
6. 问卷题目数量控制在 {context.get("question_count", 10)} 题以内。
7. 优先使用单选、多选、评分题，减少开放题，但保留至少 1 道开放题。
8. 题目语言要适合普通用户理解，避免行业黑话、诱导性措辞或隐私敏感信息。
9. 每道题都要给出 CSV 字段名，field_name 只能使用英文字母、数字和下划线，且以字母开头。
10. 输出必须是合法 JSON，不要输出 Markdown。

输出格式必须严格为：
{{
  "survey_title": "string",
  "survey_description": "string",
  "target_respondents": "string",
  "research_goal": "string",
  "pain_points": [],
  "questions": [
    {{
      "question_id": "Q1",
      "field_name": "string",
      "question_text": "string",
      "question_type": "single_choice | multiple_choice | rating | text | number",
      "options": ["string"],
      "required": true,
      "analysis_goal": "string",
      "related_claim_id": "string or null",
      "maps_to_pain_id": "P1 or null",
      "research_purpose": "string",
      "analysis_method": "string",
      "metric_role": "background | pain_existence | pain_frequency | pain_severity | pain_priority | switching_risk | competitor_preference | solution_preference | willingness_to_pay | open_feedback",
      "theme": "string",
      "hypothesis": "string or null",
      "reason": "为什么这道题对竞品分析有价值"
    }}
  ],
  "expected_analysis_dimensions": ["string"],
  "csv_columns": ["field_name"],
  "question_pain_mapping": {{"Q1": "P1"}},
  "metadata": {{}}
}}"""


def build_brief_questionnaire_prompt(brief: dict[str, Any]) -> str:
    return f"""请根据以下 SurveyBrief 生成痛点验证型问卷：
{json.dumps(brief, ensure_ascii=False)}

生成要求：
1. 问卷必须围绕 brief.pain_points 生成，不要输出通用满意度问卷。
2. 每个核心 pain point 尽量覆盖存在性、频率或严重程度、竞品影响、解决方案偏好。
3. 非背景题必须包含 maps_to_pain_id。
4. 每道题必须可统计，并保留 field_name、analysis_goal、research_purpose、analysis_method、metric_role、reason。
5. 至少保留 1 道背景题和 1 道开放反馈题。
6. 题目数量控制在 brief.question_count 以内。
7. 输出必须是合法 JSON，不要输出 Markdown。"""


def build_brief_prompt(context: dict[str, Any]) -> str:
    return f"""请根据以下前端问答记录整理 SurveyBrief：
【qa_messages】
{json.dumps(context.get("qa_messages", []), ensure_ascii=False)}
【question_count】
{context.get("question_count", 10)}

输出字段必须包含：
- research_topic
- product_or_category
- target_respondents
- research_goal
- pain_points
- competitors
- requirements
- question_count
- metadata"""


def build_review_prompt(survey_json: dict[str, Any], context: dict[str, Any]) -> str:
    return f"""请审核以下问卷 JSON：
【survey_json】
{json.dumps(survey_json, ensure_ascii=False)}
【context】
{json.dumps(context, ensure_ascii=False)}

请输出：
{{
  "passed": true,
  "score": 0,
  "issues": [
    {{
      "severity": "low | medium | high",
      "issue": "string",
      "suggestion": "string",
      "related_question_id": "string or null",
      "related_pain_id": "string or null"
    }}
  ],
  "rewrite_instruction": "string",
  "metadata": {{}}
}}"""


def build_revision_prompt(
    survey_json: dict[str, Any],
    revision_request: str,
    report_context: dict[str, Any],
) -> str:
    return f"""【原始问卷 JSON】
{json.dumps(survey_json, ensure_ascii=False)}
【修改要求】
{revision_request}
【上下文】
{json.dumps(report_context, ensure_ascii=False)}

修改要求：
1. 不要完全推翻原问卷，除非明确要求重做。
2. 保留与核心 pain_points 强相关的问题。
3. 删除重复、模糊、无法统计或 field_name 不合法的问题。
4. 非背景题必须尽量绑定已有 pain_id。
5. 如果要求是“新增问题/补充一道题/生成新问题”，只生成新增问题，不要删除或重写已有问题。
6. 不要生成空题；除非 question_type 是 text，否则不要生成空 options。
7. 新问题不能与已有问题重复，应优先补充当前覆盖不足的 pain point 或研究目标。
8. 补齐背景题、存在性题、严重程度/频率题、竞品影响题、解决方案偏好题、开放反馈题。
9. 输出必须是合法 JSON，不要输出 Markdown。"""


def _split_pain_points(text: str) -> list[str]:
    if not text.strip():
        return []
    chunks = re.split(r"[；;\n]|(?:\d+[\.、])|(?:- )", text)
    pain_points = [chunk.strip(" ，,。") for chunk in chunks if chunk.strip(" ，,。")]
    if len(pain_points) <= 1:
        pain_points = [item.strip() for item in re.split(r"[，,、/]|以及|还有|并且", text) if item.strip()]
    return _unique_list(pain_points)


def _infer_pain_points_from_topic(topic: str, goal: str) -> list[str]:
    base = topic or goal or "该产品/场景"
    return [
        f"{base} 在关键使用场景中的体验问题是否真实存在",
        f"{base} 是否存在影响购买或续费决策的核心阻碍",
        f"{base} 的当前方案是否缺少用户最看重的能力或服务",
    ]


def _extract_competitors(text: str) -> list[str]:
    if not text.strip():
        return []
    hits = re.findall(r"[A-Za-z][A-Za-z0-9+_.-]{1,20}", text)
    return _unique_list([item for item in hits if item.lower() not in {"ai", "api", "csv", "json"}])[:6]


def _slugify(text: str) -> str:
    ascii_text = re.sub(r"[^A-Za-z0-9_]+", "_", text)
    ascii_text = re.sub(r"_+", "_", ascii_text).strip("_").lower()
    if not ascii_text or not ascii_text[0].isalpha():
        ascii_text = f"field_{ascii_text or 'value'}"
    return ascii_text[:40]


def _renumber_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for index, question in enumerate(questions, start=1):
        next_question = dict(question)
        next_question["question_id"] = f"Q{index}"
        normalized.append(next_question)
    return normalized


def _dedupe_field_names(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, int] = {}
    for question in questions:
        base = _slugify(question.get("field_name") or question.get("question_text") or question.get("question_id") or "question")
        count = seen.get(base, 0)
        question["field_name"] = base if count == 0 else f"{base}_{count + 1}"
        seen[base] = count + 1
    return questions


def _unique_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
