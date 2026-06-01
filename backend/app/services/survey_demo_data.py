import csv
from io import StringIO

from app.schemas.survey import Survey, SurveyAnalysis, SurveyQuestion, SurveyResponseBatch

PHONE_DEMO_SURVEY_PAYLOAD = {
    "survey_title": "智能手机换机与购买决策验证问卷",
    "survey_description": "用于验证手机用户在换机、预算、影像、续航和 AI 功能上的真实偏好。",
    "target_respondents": "最近 12 个月内购买过手机，或未来 6 个月有换机计划的用户",
    "research_goal": "验证公开竞品分析中关于手机购买驱动、功能敏感度和切换风险的用户侧假设。",
    "questions": [
        {
            "question_id": "Q1",
            "field_name": "purchase_priority",
            "question_text": "你购买手机时最优先考虑的因素是什么？",
            "question_type": "single_choice",
            "options": ["价格", "影像拍照", "电池续航", "系统流畅度", "品牌生态", "AI 功能"],
            "required": True,
            "analysis_goal": "验证用户购买手机时最核心的决策因素。",
            "related_claim_id": None,
            "reason": "帮助判断竞品宣传重点是否与真实购买动机一致。",
        },
        {
            "question_id": "Q2",
            "field_name": "current_brand",
            "question_text": "你目前主要使用的手机品牌是？",
            "question_type": "single_choice",
            "options": ["Apple", "Huawei", "Xiaomi", "OPPO", "vivo", "Samsung", "其他"],
            "required": True,
            "analysis_goal": "识别样本当前品牌结构，用于解释切换意愿。",
            "related_claim_id": None,
            "reason": "不同品牌用户对生态、价格和功能的敏感度可能不同。",
        },
        {
            "question_id": "Q3",
            "field_name": "battery_satisfaction",
            "question_text": "你对当前手机续航的满意度如何？",
            "question_type": "rating",
            "options": ["1", "2", "3", "4", "5"],
            "required": True,
            "analysis_goal": "验证续航是否是用户真实痛点。",
            "related_claim_id": None,
            "reason": "续航满意度低会支持竞品在电池容量和快充上的差异化诉求。",
        },
        {
            "question_id": "Q4",
            "field_name": "camera_importance",
            "question_text": "影像拍照能力对你购买手机的重要程度如何？",
            "question_type": "rating",
            "options": ["1", "2", "3", "4", "5"],
            "required": True,
            "analysis_goal": "验证影像能力是否仍是高优先级卖点。",
            "related_claim_id": None,
            "reason": "判断影像卖点是否值得在竞品分析中作为强竞争维度。",
        },
        {
            "question_id": "Q5",
            "field_name": "switching_reason",
            "question_text": "什么原因最可能让你更换到另一个手机品牌？",
            "question_type": "multiple_choice",
            "options": ["价格更合适", "续航更强", "拍照更好", "系统更流畅", "AI 功能更实用", "售后服务更好"],
            "required": True,
            "analysis_goal": "验证品牌切换风险的主要触发因素。",
            "related_claim_id": None,
            "reason": "帮助判断竞品在哪些维度最可能撬动用户迁移。",
        },
        {
            "question_id": "Q6",
            "field_name": "max_budget",
            "question_text": "你下一台手机的最高预算大约是多少元？",
            "question_type": "number",
            "options": [],
            "required": True,
            "analysis_goal": "验证目标用户价格带和付费上限。",
            "related_claim_id": None,
            "reason": "预算分布可用于判断高端化策略或性价比策略是否更合适。",
        },
        {
            "question_id": "Q7",
            "field_name": "ai_feature_interest",
            "question_text": "你对手机 AI 功能的兴趣程度如何？",
            "question_type": "single_choice",
            "options": ["非常感兴趣", "比较感兴趣", "一般", "不太感兴趣", "完全不感兴趣"],
            "required": True,
            "analysis_goal": "验证 AI 功能是否能成为购买或换机驱动。",
            "related_claim_id": None,
            "reason": "AI 功能是新一代手机竞争叙事，但需要验证用户是否真实在意。",
        },
        {
            "question_id": "Q8",
            "field_name": "open_feedback",
            "question_text": "你对当前手机最不满意的一点是什么？",
            "question_type": "text",
            "options": [],
            "required": False,
            "analysis_goal": "收集结构化题目未覆盖的真实痛点。",
            "related_claim_id": None,
            "reason": "开放反馈可为后续访谈或产品定位提供线索。",
        },
    ],
    "expected_analysis_dimensions": ["购买驱动", "续航痛点", "影像重要性", "品牌切换风险", "预算价格带", "AI 功能兴趣"],
    "csv_columns": [
        "purchase_priority",
        "current_brand",
        "battery_satisfaction",
        "camera_importance",
        "switching_reason",
        "max_budget",
        "ai_feature_interest",
        "open_feedback",
    ],
}

PHONE_DEMO_RESPONSE_CSV = """purchase_priority,current_brand,battery_satisfaction,camera_importance,switching_reason,max_budget,ai_feature_interest,open_feedback
电池续航,Apple,3,5,续航更强|拍照更好,6999,比较感兴趣,电池掉电太快
影像拍照,Huawei,4,5,拍照更好|AI 功能更实用,5999,非常感兴趣,夜景拍照还想更稳
价格,Xiaomi,4,4,价格更合适|续航更强,3999,一般,广告和预装应用影响体验
系统流畅度,OPPO,3,4,系统更流畅|售后服务更好,4599,比较感兴趣,用久了会卡
电池续航,vivo,2,4,续航更强|价格更合适,4299,一般,续航焦虑明显
品牌生态,Apple,4,5,系统更流畅|拍照更好,8999,比较感兴趣,信号偶尔不好
AI 功能,Huawei,4,4,AI 功能更实用|续航更强,6999,非常感兴趣,希望 AI 摘要更准确
电池续航,Samsung,3,5,续航更强|拍照更好,7999,比较感兴趣,发热明显
价格,Xiaomi,5,3,价格更合适|系统更流畅,2999,一般,系统弹窗太多
影像拍照,OPPO,4,5,拍照更好|售后服务更好,4999,比较感兴趣,人像拍照是刚需
系统流畅度,Apple,4,4,系统更流畅|价格更合适,7999,一般,价格太高
电池续航,Huawei,5,4,续航更强|AI 功能更实用,5999,非常感兴趣,快充体验很好
价格,vivo,3,3,价格更合适|续航更强,3499,一般,希望中端机质感更好
影像拍照,Xiaomi,4,5,拍照更好|AI 功能更实用,4999,比较感兴趣,长焦很重要
电池续航,OPPO,2,4,续航更强|系统更流畅,3999,不太感兴趣,一天两充很麻烦
品牌生态,Apple,5,5,拍照更好|系统更流畅,9999,比较感兴趣,生态粘性强
AI 功能,Huawei,4,4,AI 功能更实用|售后服务更好,6999,非常感兴趣,通话摘要很有用
电池续航,其他,3,3,续航更强|价格更合适,2599,一般,预算有限
价格,Samsung,4,5,价格更合适|拍照更好,6999,不太感兴趣,维修成本高
系统流畅度,vivo,3,4,系统更流畅|续航更强,4299,比较感兴趣,系统动画要更顺滑
影像拍照,Apple,4,5,拍照更好|AI 功能更实用,8999,比较感兴趣,希望中文 AI 更好用
电池续航,Xiaomi,4,4,续航更强|价格更合适,3999,一般,快充很重要
AI 功能,OPPO,3,4,AI 功能更实用|系统更流畅,4999,非常感兴趣,想要更好用的图片编辑
价格,Huawei,5,4,价格更合适|售后服务更好,5999,比较感兴趣,价格上涨影响换机
电池续航,vivo,3,3,续航更强|拍照更好,3699,一般,拍视频发热
影像拍照,Samsung,4,5,拍照更好|系统更流畅,7999,比较感兴趣,屏幕观感很好
系统流畅度,Xiaomi,3,4,系统更流畅|AI 功能更实用,4499,比较感兴趣,希望系统更稳定
电池续航,Apple,3,5,续航更强|价格更合适,7999,一般,充电速度慢
品牌生态,Huawei,5,4,AI 功能更实用|续航更强,6999,非常感兴趣,跨设备协同好用
价格,OPPO,4,3,价格更合适|售后服务更好,3299,不太感兴趣,只要稳定耐用
"""


def build_phone_demo_response_csv_for_survey(survey: Survey) -> str:
    rows = list(csv.DictReader(StringIO(PHONE_DEMO_RESPONSE_CSV)))
    return _build_response_csv_for_survey_rows(survey, rows)


def normalize_phone_demo_response_csv_for_survey(survey: Survey, content: str) -> str:
    reader = csv.DictReader(StringIO(content.lstrip("\ufeff")))
    rows = [
        {key: (value or "").strip() for key, value in row.items()}
        for row in reader
        if any((value or "").strip() for value in row.values())
    ]
    if not rows:
        rows = list(csv.DictReader(StringIO(PHONE_DEMO_RESPONSE_CSV)))
    return _build_response_csv_for_survey_rows(survey, rows)


def _build_response_csv_for_survey_rows(survey: Survey, rows: list[dict[str, str]]) -> str:
    output = StringIO()
    field_names = [question.field_name for question in survey.questions]
    writer = csv.DictWriter(output, fieldnames=field_names)
    writer.writeheader()
    questions_by_field = {question.field_name: question for question in survey.questions}
    for index, source_row in enumerate(rows):
        writer.writerow(
            {
                field_name: _demo_answer_for_field(field_name, questions_by_field[field_name], source_row, index)
                for field_name in field_names
            }
        )
    return output.getvalue()


def build_phone_demo_analysis(
    survey: Survey,
    batch: SurveyResponseBatch,
    raw_stats: dict,
) -> SurveyAnalysis:
    stats_by_field = _stats_by_field(raw_stats)
    priority = stats_by_field.get("purchase_priority")
    switching = stats_by_field.get("switching_reason")
    budget = stats_by_field.get("max_budget")
    ai_interest = stats_by_field.get("ai_feature_interest")
    battery = stats_by_field.get("battery_satisfaction")
    camera = stats_by_field.get("camera_importance")
    premium = stats_by_field.get("premium_willingness")
    top_priority = _top_label(priority.get("distribution", {}) if priority else {})
    top_switching = _top_label(switching.get("distribution", {}) if switching else {})
    top_premium = _top_label(premium.get("distribution", {}) if premium else {})
    high_ai_ratio = 0.0
    if ai_interest:
        high_ai_ratio = _ratio(ai_interest.get("distribution", {}), "非常感兴趣") + _ratio(ai_interest.get("distribution", {}), "比较感兴趣")
    confidence = 0.74 if batch.valid_count >= 30 else 0.62
    summary_parts = [f"手机问卷样例共 {batch.valid_count} 份有效反馈"]
    if top_priority != "暂无":
        summary_parts.append(f"购买优先级最高的是“{top_priority}”")
    if top_switching != "暂无":
        summary_parts.append(f"品牌切换最常见触发因素是“{top_switching}”")
    if camera and camera.get("average") is not None:
        summary_parts.append(f"影像重要性均分 {camera['average']}")
    if battery and battery.get("average") is not None:
        summary_parts.append(f"续航满意度均分 {battery['average']}")
    if top_premium != "暂无":
        summary_parts.append(f"付费溢价意愿最高频选项为“{top_premium}”")
    if high_ai_ratio:
        summary_parts.append(f"对 AI 功能表示非常或比较感兴趣的比例约 {high_ai_ratio:.0%}")

    dashboard_summary = "；".join(summary_parts) + "。"
    key_findings = []
    if top_priority != "暂无":
        key_findings.append(
            {
                "finding": f"购买决策中“{top_priority}”最突出，说明手机竞品对比需要重点展示该维度。",
                "supporting_questions": [_question_id_for_field(survey, "purchase_priority")],
                "confidence": confidence,
                "explanation": "该结论来自单选题最高频选项，适合作为演示性方向判断。",
            }
        )
    if top_switching != "暂无":
        key_findings.append(
            {
                "finding": f"品牌切换风险主要由“{top_switching}”触发，价格和体验类因素也有明显影响。",
                "supporting_questions": [_question_id_for_field(survey, "switching_reason")],
                "confidence": confidence,
                "explanation": "多选题显示用户迁移通常不是单一因素，而是功能、价格和体验共同作用。",
            }
        )
    if top_premium != "暂无":
        key_findings.append(
            {
                "finding": f"付费意愿题中“{top_premium}”最高频，可作为高端化或功能溢价判断的补充信号。",
                "supporting_questions": [_question_id_for_field(survey, "premium_willingness")],
                "confidence": 0.7,
                "explanation": "该结论来自新增付费意愿题，适合用于新版问卷的演示分析。",
            }
        )
    if high_ai_ratio:
        key_findings.append(
            {
                "finding": f"AI 功能已有可见兴趣，约 {high_ai_ratio:.0%} 的样本选择非常或比较感兴趣。",
                "supporting_questions": [_question_id_for_field(survey, "ai_feature_interest")],
                "confidence": 0.68,
                "explanation": "AI 功能可以作为竞争叙事，但仍需结合使用场景验证真实付费转化。",
            }
        )

    question_level_analysis = []
    for question in survey.questions:
        question_stats = stats_by_field.get(question.field_name)
        if not question_stats:
            continue
        question_level_analysis.append(_question_analysis(question, question_stats))

    willingness_to_pay = None
    if premium and top_premium != "暂无":
        willingness_to_pay = f"付费溢价最高频选项为“{top_premium}”，说明用户对功能提升的额外支付意愿需要分层判断。"
    if budget and budget.get("median") is not None:
        budget_signal = f"样例预算中位数为 {budget['median']} 元，说明样本主要集中在中高端价格带。"
        willingness_to_pay = f"{budget_signal} {willingness_to_pay or ''}".strip()

    switching_risk = None
    if top_switching != "暂无":
        switching_risk = f"最强切换触发因素为“{top_switching}”，其次应关注价格和系统体验。"

    return SurveyAnalysis(
        survey_id=survey.survey_id,
        batch_id=batch.batch_id,
        summary=dashboard_summary,
        sample_summary={
            "sample_size": batch.sample_size,
            "valid_count": batch.valid_count,
            "invalid_count": batch.invalid_count,
            "limitations": ["这是用于前端演示的手机问卷样例数据", "样本不是随机抽样，不能代表完整市场"],
        },
        key_findings=key_findings,
        question_level_analysis=question_level_analysis,
        claim_updates=[
            {
                "claim_id": survey.source_claim_ids[0] if survey.source_claim_ids else "demo_claim_phone_001",
                "original_claim": "手机竞品差异应重点关注续航、影像、价格带和 AI 功能。",
                "survey_result": "样例数据支持这些维度均有用户侧信号，其中续航和影像最突出。",
                "impact": "support",
                "recommended_revision": "将续航和影像作为强优先级维度，AI 功能作为需继续验证的新兴维度。",
            }
        ],
        user_pain_points=["续航焦虑", "发热", "系统卡顿或弹窗", "高端机价格压力", "AI 功能实用性仍需验证"],
        willingness_to_pay=willingness_to_pay,
        switching_risk=switching_risk,
        survey_evidence={
            "type": "survey",
            "survey_id": survey.survey_id,
            "batch_id": batch.batch_id,
            "sample_size": batch.sample_size,
            "valid_count": batch.valid_count,
            "summary": dashboard_summary,
            "confidence": confidence,
            "related_claim_ids": survey.source_claim_ids,
            "limitations": ["样例数据仅用于演示", "样本来源可能存在偏差"],
            "metadata": {"source_type": "survey", "demo": True, "raw_stats": raw_stats},
        },
        dashboard_summary=dashboard_summary,
    )


def _top_label(distribution: dict) -> str:
    if not distribution:
        return "暂无"
    return max(distribution.items(), key=lambda item: int(item[1]["count"]))[0]


def _ratio(distribution: dict, label: str) -> float:
    value = distribution.get(label)
    return float(value.get("ratio", 0.0)) if isinstance(value, dict) else 0.0


def _format_distribution(distribution: dict) -> str:
    return " / ".join(
        f"{label}: {value['count']} ({float(value['ratio']):.0%})"
        for label, value in distribution.items()
    )


def _stats_by_field(raw_stats: dict) -> dict:
    return {
        stats.get("field_name"): stats
        for stats in raw_stats.get("questions", {}).values()
        if stats.get("field_name")
    }


def _question_id_for_field(survey: Survey, field_name: str) -> str:
    for question in survey.questions:
        if question.field_name == field_name:
            return question.question_id
    return field_name


def _question_analysis(question: SurveyQuestion, stats: dict) -> dict:
    if "distribution" in stats:
        top_option = _top_label(stats["distribution"])
        return {
            "question_id": question.question_id,
            "field_name": question.field_name,
            "summary": f"最高频选项为“{top_option}”。",
            "notable_stats": [_format_distribution(stats["distribution"])],
        }
    if question.question_type in {"rating", "number"}:
        notable_stats = [
            f"average={stats.get('average')}",
            f"median={stats.get('median')}",
            f"min={stats.get('min')}",
            f"max={stats.get('max')}",
        ]
        return {
            "question_id": question.question_id,
            "field_name": question.field_name,
            "summary": f"{question.question_text} 的均值为 {stats.get('average')}，中位数为 {stats.get('median')}。",
            "notable_stats": [item for item in notable_stats if not item.endswith("None")],
        }
    return {
        "question_id": question.question_id,
        "field_name": question.field_name,
        "summary": f"收集到 {stats.get('answer_count', 0)} 条非空文本反馈。",
        "notable_stats": [str(item) for item in stats.get("text_samples", [])[:5]],
    }


def _demo_answer_for_field(field_name: str, question: SurveyQuestion, source_row: dict[str, str], index: int) -> str:
    if field_name in source_row:
        return source_row[field_name]
    if field_name == "premium_willingness":
        options = ["不愿意额外支付", "1-300 元", "301-800 元", "801-1500 元", "1500 元以上"]
        return options[index % len(options)]
    if question.question_type == "single_choice":
        return question.options[index % len(question.options)] if question.options else ""
    if question.question_type == "multiple_choice":
        return "|".join(question.options[:2]) if question.options else ""
    if question.question_type == "rating":
        return question.options[min(index % len(question.options), len(question.options) - 1)] if question.options else "4"
    if question.question_type == "number":
        return source_row.get("max_budget") or str(3000 + index * 200)
    if question.question_type == "text":
        return source_row.get("open_feedback") or "样例开放反馈"
    return ""
