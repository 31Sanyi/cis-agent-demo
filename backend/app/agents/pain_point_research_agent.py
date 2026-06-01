from __future__ import annotations

import re
from typing import Any


class PainPointResearchAgent:
    """Extracts user-verifiable product pain points from planner and report context."""

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        task = context.get("task") or {}
        planner_context = context.get("planner_context") or {}
        claims = [claim for claim in context.get("claims_json") or [] if isinstance(claim, dict)]
        competitors = list(task.get("competitors") or [])
        candidates: list[dict[str, Any]] = []

        for claim in claims:
            confidence = _safe_float(claim.get("confidence"), 0.55)
            text = str(claim.get("text") or "").strip()
            if not text:
                continue
            if confidence <= 0.7 or _contains_pain_signal(text):
                candidates.append(
                    {
                        "source": text,
                        "related_claim_ids": [str(claim.get("claim_id"))] if claim.get("claim_id") else [],
                        "related_competitors": [str(claim.get("competitor"))] if claim.get("competitor") else [],
                        "confidence": max(0.4, min(confidence, 0.72)),
                    }
                )

        survey_inputs = planner_context.get("survey_inputs") or {}
        for source in [
            *list(planner_context.get("missing_information") or []),
            *list(planner_context.get("assumptions") or []),
            *list(survey_inputs.get("hypotheses") or []),
            *list(survey_inputs.get("question_themes") or []),
        ]:
            text = str(source).strip()
            if text:
                candidates.append(
                    {
                        "source": text,
                        "related_claim_ids": [],
                        "related_competitors": [],
                        "confidence": 0.48 if not _contains_pain_signal(text) else 0.55,
                    }
                )

        if not candidates:
            product = task.get("product_name") or "目标产品"
            industry = task.get("industry") or "该品类"
            fallback_sources = [
                f"{product} 在 {industry} 场景下的核心使用痛点是否真实存在",
                "用户是否会因为关键体验不足转向竞品",
                "用户是否愿意为解决核心痛点支付额外成本",
            ]
            candidates = [
                {"source": item, "related_claim_ids": [], "related_competitors": competitors[:2], "confidence": 0.42}
                for item in fallback_sources
            ]

        pain_points = []
        seen: set[str] = set()
        for candidate in candidates:
            if len(pain_points) >= 6:
                break
            source = str(candidate["source"])
            pain = _to_pain_statement(source, task)
            key = re.sub(r"\W+", "", pain.lower())
            if key in seen:
                continue
            seen.add(key)
            pain_id = f"P{len(pain_points) + 1}"
            related_competitors = candidate.get("related_competitors") or _competitors_in_text(source, competitors)
            pain_points.append(
                {
                    "pain_id": pain_id,
                    "pain_point": pain,
                    "source_from_report": source[:300],
                    "related_claim_ids": candidate.get("related_claim_ids") or [],
                    "related_competitors": related_competitors,
                    "affected_user_scenarios": _scenarios_from_text(source, task),
                    "severity_assumption": _severity_from_text(source),
                    "confidence": _safe_float(candidate.get("confidence"), 0.5),
                    "why_need_survey": "公开资料只能提供间接信号，需要用户反馈验证该痛点是否真实存在、影响多大以及是否会驱动竞品切换。",
                    "research_questions": [
                        "目标用户是否真实遇到该痛点？",
                        "该痛点出现频率和严重程度如何？",
                        "该痛点是否影响购买、续费、推荐或转向竞品？",
                    ],
                    "metadata": {"source": "pain_point_research_agent"},
                }
            )

        while len(pain_points) < 3:
            pain_id = f"P{len(pain_points) + 1}"
            pain_points.append(
                {
                    "pain_id": pain_id,
                    "pain_point": f"{task.get('product_name') or '目标产品'} 的用户侧体验痛点仍需进一步验证",
                    "source_from_report": "报告和 Planner 上下文不足，使用低置信度 fallback 痛点。",
                    "related_claim_ids": [],
                    "related_competitors": competitors[:2],
                    "affected_user_scenarios": ["购买决策", "持续使用", "竞品替代评估"],
                    "severity_assumption": "medium",
                    "confidence": 0.4,
                    "why_need_survey": "当前公开证据不足以支撑强结论，需要通过用户反馈补齐。",
                    "research_questions": ["该痛点是否存在？", "它是否影响购买或切换？"],
                    "metadata": {"source": "fallback"},
                }
            )

        return {"pain_points": pain_points[:6]}


def _contains_pain_signal(text: str) -> bool:
    return any(
        keyword in text.lower()
        for keyword in [
            "pain",
            "risk",
            "weak",
            "缺",
            "不足",
            "痛点",
            "抱怨",
            "不满",
            "风险",
            "低",
            "贵",
            "切换",
            "续航",
            "价格",
            "体验",
        ]
    )


def _to_pain_statement(source: str, task: dict[str, Any]) -> str:
    text = source.strip(" 。；;")
    if _contains_pain_signal(text):
        return text[:120]
    product = task.get("product_name") or "目标产品"
    return f"用户是否认为{product}在“{text[:80]}”方面存在影响决策的痛点"


def _competitors_in_text(text: str, competitors: list[str]) -> list[str]:
    normalized = text.lower()
    return [competitor for competitor in competitors if competitor and competitor.lower() in normalized]


def _scenarios_from_text(text: str, task: dict[str, Any]) -> list[str]:
    scenarios = []
    if any(keyword in text for keyword in ["购买", "预算", "价格", "付费", "pricing"]):
        scenarios.append("购买决策")
    if any(keyword in text for keyword in ["切换", "替代", "竞品", "switch"]):
        scenarios.append("竞品替代评估")
    if any(keyword in text for keyword in ["使用", "体验", "功能", "workflow"]):
        scenarios.append("日常使用")
    return scenarios or [task.get("industry") or "目标使用场景"]


def _severity_from_text(text: str) -> str:
    if any(keyword in text.lower() for keyword in ["high", "严重", "核心", "关键", "强"]):
        return "high"
    if any(keyword in text.lower() for keyword in ["low", "轻微", "弱"]):
        return "low"
    return "medium"


def _safe_float(value: Any, fallback: float) -> float:
    try:
        return round(max(0.0, min(1.0, float(value))), 2)
    except (TypeError, ValueError):
        return fallback
