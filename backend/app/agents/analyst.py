from collections import defaultdict

from app.agents.base import run_with_trace
from app.domain import domain_pack_reference, resolve_domain_pack
from app.schemas import (
    AnalystInput,
    AnalystOutput,
    CapabilityBucket,
    CapabilityMap,
    CapabilitySignal,
    Evidence,
    FeatureTree,
    PricingModel,
    ProductProfile,
    SwotAnalysis,
    SwotItem,
    UserPersona,
)
from app.services.evidence_relevance_service import is_relevant_evidence
from app.services.trace_service import TraceService


FEATURE_KEYWORDS = {
    "AI": ["ai", "artificial intelligence", "智能", "人工智能"],
    "automation": ["automation", "automated", "自动化"],
    "collaboration": ["collaboration", "collaborative", "team", "协作", "团队", "办公"],
    "pricing": ["pricing", "price", "plan", "定价", "价格", "套餐"],
    "integration": ["integration", "integrations", "集成"],
    "analytics": ["analytics", "analysis", "dashboard", "分析", "看板"],
    "security": ["security", "compliance", "安全", "合规"],
    "mobile": ["mobile", "app", "移动端"],
    "API": ["api", "developer", "接口", "开发者"],
    "workflow": ["workflow", "process", "流程"],
}

PRICING_KEYWORDS = [
    "free",
    "trial",
    "pricing",
    "subscription",
    "enterprise",
    "plan",
    "quote",
    "免费",
    "试用",
    "订阅",
    "企业版",
    "套餐",
    "定价",
    "价格",
]
PERSONA_KEYWORDS = {
    "企业团队": ["enterprise", "procurement", "企业"],
    "团队用户": ["team", "operations", "团队"],
    "开发者": ["developer", "engineering", "开发者"],
    "市场团队": ["marketer", "marketing", "市场"],
    "产品团队": ["product team", "product manager", "产品团队", "产品经理"],
    "学生": ["student", "education", "学生"],
}


class AnalystAgent:
    name = "AnalystAgent"

    def __init__(self, trace_service: TraceService):
        self.trace_service = trace_service

    def run(self, input_data: AnalystInput) -> AnalystOutput:
        task = input_data.task

        def produce() -> AnalystOutput:
            if input_data.analyst_mode == "mock":
                return self._mock_output(input_data, fallback_reason=None)
            if input_data.analyst_mode == "llm":
                return self._evidence_output(
                    input_data,
                    fallback_reason="analyst_mode=llm is not implemented in this phase; fallback to evidence mode.",
                )
            return self._evidence_output(input_data, fallback_reason=None)

        return run_with_trace(
            trace_service=self.trace_service,
            task_id=task.task_id,
            agent_name=self.name,
            to_agent="ReportWriterAgent",
            message_type="analysis",
            schema_name="AnalystOutput",
            input_summary=f"analyst_mode_requested={input_data.analyst_mode}; analyze {len(input_data.evidence)} evidence records",
            retry_count=input_data.retry_count,
            fn=produce,
        )

    def _mock_output(self, input_data: AnalystInput, fallback_reason: str | None) -> AnalystOutput:
        task = input_data.task
        ids = self._ids(input_data.evidence)
        selected_dimensions = self._selected_dimensions(input_data)
        capability_map = self._build_capability_map(task, input_data.evidence, competitor_order=task.competitors)
        diagnostics = self._diagnostics(
            input_data,
            "mock",
            ids,
            fallback_reason=fallback_reason,
            evidence_by_competitor=self._group_by_competitor(input_data.evidence, task.competitors),
            extracted_fields_by_competitor={
                competitor: {"profile": 1, "feature": 1, "pricing": 1, "persona": 1} for competitor in task.competitors
            },
        )
        competitor_analysis = {
            competitor: {
                "positioning": f"{competitor} is represented by mock competitor knowledge.",
                "features": ["collaboration", "workflow"],
                "pricing": ["paid/enterprise signal"],
                "persona": ["enterprise team"],
                "evidence_ids": [item.evidence_id for item in input_data.evidence if item.competitor == competitor] or ids[:1],
                "insufficient_evidence": False,
            }
            for competitor in task.competitors
        }
        profile = ProductProfile(
            product_name=task.product_name,
            positioning=""
            if input_data.force_invalid_extraction
            else f"{task.product_name} is a structured competitor analysis workspace.",
            target_segments=[]
            if input_data.force_invalid_extraction
            else ["product marketing team", "strategy team", "sales enablement team"],
            strengths=["traceable evidence", "structured schema", "QA feedback loop"],
            weaknesses=["current demo still uses simplified extraction rules"],
            evidence_ids=ids[:2],
            extensions={
                "domain": {
                    "region": task.region,
                    "industry": task.industry,
                    "domain_pack": domain_pack_reference(
                        resolve_domain_pack(task),
                        industry_label=task.industry,
                        metadata={"owner": "AnalystAgent", "mode": "mock"},
                    ).model_dump(mode="json"),
                },
                "workflow": {
                    "analyst_mode": "mock",
                    "selected_dimensions": selected_dimensions,
                    "competitor_analysis": competitor_analysis,
                    "capability_map": capability_map.model_dump(mode="json"),
                },
            },
            custom_dimensions={
                "region": task.region,
                "industry": task.industry,
                "analyst_mode": "mock",
                "selected_dimensions": selected_dimensions,
                "competitor_analysis": competitor_analysis,
            },
        )
        feature_tree = FeatureTree(
            core_features=self._legacy_feature_tree_projection(capability_map) or {competitor: ["collaboration", "workflow", "pricing"] for competitor in task.competitors},
            differentiators=self._legacy_differentiators(capability_map) or ["claim-to-evidence traceability", "manual review fallback"],
            evidence_ids=ids,
        )
        pricing = PricingModel(
            model="tiered SaaS benchmark",
            tiers=[f"{competitor}: starter/team/enterprise signals" for competitor in task.competitors],
            pricing_notes="Competitors usually package collaboration and integration capability into higher tiers.",
            evidence_ids=ids[1:3] or ids[:1],
        )
        persona = UserPersona(
            persona_name="competitor intelligence owner",
            goals=["reduce manual research time", "keep conclusions source-backed", "standardize report format"],
            pain_points=["sources are scattered", "evidence quality is opaque", "QA takes time"],
            buying_triggers=["new market entry", "quarterly planning", "sales battlecard refresh"],
            evidence_ids=ids[2:4] or ids[:1],
        )
        swot = self._build_mock_swot(task.competitors, ids, selected_dimensions)
        diagnostics.update(
            {
                "selected_dimensions": selected_dimensions,
                "selected_dimension_count": len(selected_dimensions),
                "swot_item_count": self._count_swot_items(swot),
                "rework_context_applied": bool(input_data.rework_context),
            }
        )
        return AnalystOutput(
            product_profile=profile,
            feature_tree=feature_tree,
            capability_map=capability_map,
            pricing_model=pricing,
            user_persona=persona,
            swot=swot,
            diagnostics=diagnostics,
        )

    def _evidence_output(self, input_data: AnalystInput, fallback_reason: str | None) -> AnalystOutput:
        task = input_data.task
        selected_dimensions = self._selected_dimensions(input_data)
        usable_evidence = [item for item in input_data.evidence if item.relevance_level in {"high", "medium"}]
        weak_evidence = [item for item in input_data.evidence if item.relevance_level == "low"]
        evidence_by_competitor = self._group_by_competitor(usable_evidence, task.competitors)
        all_evidence_by_competitor = self._group_by_competitor(input_data.evidence, task.competitors)
        ids = self._ids(usable_evidence)
        capability_map = self._build_capability_map(task, usable_evidence, competitor_order=task.competitors)
        competitor_analysis: dict[str, dict] = {}
        aggregate_feature_hits: dict[str, list[Evidence]] = defaultdict(list)
        pricing_tiers: list[str] = []
        persona_goals: list[str] = []
        persona_pain_points: list[str] = []
        persona_triggers: list[str] = []
        aggregate_persona_labels: list[str] = []
        extracted_fields_by_competitor: dict[str, dict[str, int]] = {}
        evidence_used_by_competitor: dict[str, list[str]] = {}

        for competitor in task.competitors:
            competitor_evidence = sorted(evidence_by_competitor.get(competitor, []), key=lambda item: item.confidence, reverse=True)
            competitor_ids = self._ids(competitor_evidence)
            feature_hits = self._feature_hits(task, competitor_evidence)
            pricing_evidence = self._keyword_evidence(competitor_evidence, PRICING_KEYWORDS)
            persona_hits = self._persona_hits(competitor_evidence)
            insufficient = len(competitor_evidence) < 1 or (len(feature_hits) + len(pricing_evidence) + len(persona_hits)) < 1

            feature_names = list(feature_hits.keys()) or ["insufficient evidence"]
            pricing_labels = self._pricing_tiers(pricing_evidence)
            persona_labels = list(persona_hits.keys()) or ["Evidence-insufficient persona"]
            aggregate_persona_labels.extend([item for item in persona_labels if item != "Evidence-insufficient persona"])
            positioning = (
                "Evidence is insufficient for a confident conclusion."
                if insufficient
                else f"{competitor} positioning is inferred only from its own public evidence: {self._compact(self._evidence_text(competitor_evidence[0]))}"
            )

            competitor_analysis[competitor] = {
                "positioning": positioning,
                "features": feature_names,
                "pricing": pricing_labels,
                "persona": persona_labels,
                "evidence_ids": competitor_ids,
                "insufficient_evidence": insufficient,
            }
            evidence_used_by_competitor[competitor] = competitor_ids
            extracted_fields_by_competitor[competitor] = {
                "profile": 0 if insufficient else 1,
                "feature": len(feature_hits),
                "pricing": len(pricing_evidence),
                "persona": len(persona_hits),
            }
            for feature, values in feature_hits.items():
                aggregate_feature_hits[feature].extend(values)
            pricing_tiers.append(f"{competitor}: {', '.join(pricing_labels)}")
            persona_goals.append(f"{competitor}: evaluate fit for {', '.join(persona_labels[:2])}")
            persona_pain_points.append(f"{competitor}: needs more official, pricing, and user-feedback evidence cross-checks")
            persona_triggers.append(f"{competitor}: product selection and competitor replacement")
        missing_competitors = [competitor for competitor, records in evidence_by_competitor.items() if not records]
        insufficient = bool(missing_competitors) or any(item["insufficient_evidence"] for item in competitor_analysis.values())
        diagnostics = self._diagnostics(
            input_data,
            "evidence",
            ids,
            fallback_reason=fallback_reason or ("Evidence is insufficient for one or more competitors." if insufficient else None),
            insufficient=insufficient,
            feature_count=sum(item["feature"] for item in extracted_fields_by_competitor.values()),
            pricing_count=sum(item["pricing"] for item in extracted_fields_by_competitor.values()),
            persona_count=sum(item["persona"] for item in extracted_fields_by_competitor.values()),
            evidence_by_competitor=evidence_by_competitor,
            extracted_fields_by_competitor=extracted_fields_by_competitor,
            evidence_used_by_competitor=evidence_used_by_competitor,
        )
        diagnostics.update(
            {
                "insufficient_relevant_evidence": insufficient,
                "relevant_evidence_count": len(usable_evidence),
                "low_relevance_evidence_count": len(weak_evidence),
                "unrelated_evidence_count": sum(1 for item in input_data.evidence if item.relevance_level == "unrelated"),
                "all_evidence_count_by_competitor": {
                    competitor: len(records) for competitor, records in all_evidence_by_competitor.items()
                },
                "content_source_used": self._content_source_summary(usable_evidence),
                "capability_area_count": len(capability_map.aggregate_capabilities),
                "unmapped_capability_signal_count": len(capability_map.unmapped_signals),
                "selected_dimensions": selected_dimensions,
                "selected_dimension_count": len(selected_dimensions),
            }
        )
        profile = ProductProfile(
            product_name=task.product_name,
            positioning=""
            if input_data.force_invalid_extraction
            else (
                "Evidence is insufficient for a confident conclusion."
                if insufficient
                else f"{task.product_name} compares {', '.join(task.competitors)} using competitor-specific public evidence."
            ),
            target_segments=[]
            if input_data.force_invalid_extraction
            else (["Evidence is insufficient for a confident conclusion."] if insufficient else ["enterprise team", "product team"]),
            strengths=self._strengths_from_features(dict(aggregate_feature_hits)) or ["Evidence is insufficient for a confident conclusion."],
            weaknesses=["Conclusions remain limited by available public evidence coverage per competitor."],
            evidence_ids=ids[: min(5, len(ids))],
            extensions={
                "domain": {
                    "region": task.region,
                    "industry": task.industry,
                    "domain_pack": domain_pack_reference(
                        resolve_domain_pack(task),
                        industry_label=task.industry,
                        metadata={"owner": "AnalystAgent", "mode": "evidence"},
                    ).model_dump(mode="json"),
                },
                "workflow": {
                    "analyst_mode": "evidence",
                    "selected_dimensions": selected_dimensions,
                    "insufficient_evidence": insufficient,
                    "supporting_evidence_ids": ids,
                    "competitor_analysis": competitor_analysis,
                    "capability_map": capability_map.model_dump(mode="json"),
                },
            },
            custom_dimensions={
                "region": task.region,
                "industry": task.industry,
                "analyst_mode": "evidence",
                "selected_dimensions": selected_dimensions,
                "insufficient_evidence": insufficient,
                "supporting_evidence_ids": ids,
                "competitor_analysis": competitor_analysis,
            },
        )
        feature_tree = FeatureTree(
            core_features=self._legacy_feature_tree_projection(capability_map) or {"insufficient evidence": ["Evidence is insufficient for a confident conclusion."]},
            differentiators=self._legacy_differentiators(capability_map) or self._strengths_from_features(dict(aggregate_feature_hits)) or ["Evidence is insufficient for a confident conclusion."],
            evidence_ids=ids,
        )
        pricing = PricingModel(
            model="Evidence-based competitor pricing summary" if not insufficient else "Evidence insufficient",
            tiers=pricing_tiers or ["Evidence is insufficient"],
            pricing_notes=self._pricing_notes([item for records in evidence_by_competitor.values() for item in records]),
            evidence_ids=[
                item.evidence_id
                for records in evidence_by_competitor.values()
                for item in self._keyword_evidence(records, PRICING_KEYWORDS)
            ]
            or ids[:1],
        )
        persona = UserPersona(
            persona_name=aggregate_persona_labels[0] if aggregate_persona_labels else "competitor evaluation team",
            goals=persona_goals or ["Evidence is insufficient for a confident conclusion."],
            pain_points=persona_pain_points or ["Need more competitor-specific evidence."],
            buying_triggers=persona_triggers or ["Evidence is insufficient for a confident conclusion."],
            evidence_ids=ids[: min(5, len(ids))],
        )
        swot = self._build_evidence_swot(
            task.competitors,
            selected_dimensions,
            evidence_by_competitor=evidence_by_competitor,
            competitor_analysis=competitor_analysis,
            aggregate_feature_hits=dict(aggregate_feature_hits),
        )
        swot, swot_refinement_summary = self._refine_swot_for_rework(
            swot,
            input_data=input_data,
            evidence_by_competitor=evidence_by_competitor,
        )
        diagnostics["swot_item_count"] = self._count_swot_items(swot)
        diagnostics["rework_context_applied"] = bool(input_data.rework_context)
        diagnostics["swot_refinement_summary"] = swot_refinement_summary
        return AnalystOutput(
            product_profile=profile,
            feature_tree=feature_tree,
            capability_map=capability_map,
            pricing_model=pricing,
            user_persona=persona,
            swot=swot,
            diagnostics=diagnostics,
        )

    def _diagnostics(
        self,
        input_data: AnalystInput,
        used_mode: str,
        ids: list[str],
        *,
        fallback_reason: str | None,
        insufficient: bool = False,
        feature_count: int = 0,
        pricing_count: int = 0,
        persona_count: int = 0,
        evidence_by_competitor: dict[str, list[Evidence]] | None = None,
        extracted_fields_by_competitor: dict[str, dict[str, int]] | None = None,
        evidence_used_by_competitor: dict[str, list[str]] | None = None,
    ) -> dict:
        grouped = evidence_by_competitor or self._group_by_competitor(input_data.evidence, input_data.task.competitors)
        evidence_count_by_competitor = {competitor: len(records) for competitor, records in grouped.items()}
        competitors_covered = [competitor for competitor, count in evidence_count_by_competitor.items() if count > 0]
        missing_competitors = [
            competitor for competitor in input_data.task.competitors if evidence_count_by_competitor.get(competitor, 0) == 0
        ]
        return {
            "analyst_mode_requested": input_data.analyst_mode,
            "analyst_mode_used": used_mode,
            "evidence_count": len(input_data.evidence),
            "evidence_used_count": len(ids),
            "extracted_profile_count": 0 if insufficient else len(competitors_covered),
            "extracted_feature_count": feature_count,
            "extracted_pricing_count": pricing_count,
            "extracted_persona_count": persona_count,
            "insufficient_evidence": insufficient,
            "fallback_used": bool(fallback_reason),
            "fallback_reason": fallback_reason,
            "analyst_fallback_reason": fallback_reason,
            "competitors_requested": input_data.task.competitors,
            "competitors_covered": competitors_covered,
            "missing_competitors": missing_competitors,
            "evidence_count_by_competitor": evidence_count_by_competitor,
            "evidence_used_by_competitor": evidence_used_by_competitor
            or {competitor: [item.evidence_id for item in records] for competitor, records in grouped.items()},
            "extracted_fields_by_competitor": extracted_fields_by_competitor or {},
        }

    @staticmethod
    def _group_by_competitor(evidence: list[Evidence], competitors: list[str]) -> dict[str, list[Evidence]]:
        grouped: dict[str, list[Evidence]] = {competitor: [] for competitor in competitors}
        if evidence and not any(item.competitor for item in evidence) and all(is_relevant_evidence(item) for item in evidence):
            for competitor in competitors:
                grouped[competitor] = list(evidence)
            return grouped
        for item in evidence:
            if item.competitor in grouped:
                grouped[item.competitor].append(item)
            elif item.competitor is None and len(competitors) == 1:
                grouped[competitors[0]].append(item)
        return grouped

    @staticmethod
    def _ids(evidence: list[Evidence]) -> list[str]:
        return [item.evidence_id for item in evidence] or ["insufficient_evidence"]

    @staticmethod
    def _dedupe(items) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for item in items:
            value = str(item).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            output.append(value)
        return output

    @staticmethod
    def _compact(text: str) -> str:
        return text[:120].replace("\n", " ")

    @staticmethod
    def _evidence_text(item: Evidence) -> str:
        return item.content_excerpt or item.snippet

    @staticmethod
    def _content_source_summary(evidence: list[Evidence]) -> dict[str, int]:
        return {
            "page_excerpt": sum(1 for item in evidence if item.content_excerpt),
            "snippet": sum(1 for item in evidence if not item.content_excerpt),
        }

    def _build_capability_map(self, task, evidence: list[Evidence], *, competitor_order: list[str]) -> CapabilityMap:
        resolved_domain_pack = resolve_domain_pack(task)
        domain_pack = domain_pack_reference(
            resolved_domain_pack,
            industry_label=task.industry,
            metadata={"owner": "AnalystAgent", "source": "capability_extraction"},
        )
        feature_taxonomy = {
            **{feature: tuple(keywords) for feature, keywords in FEATURE_KEYWORDS.items()},
            **resolved_domain_pack.feature_taxonomy,
        }
        competitor_capabilities: dict[str, list[CapabilityBucket]] = {}
        aggregate_buckets: list[CapabilityBucket] = []
        unmapped_signals: list[CapabilitySignal] = []

        for competitor in competitor_order:
            competitor_evidence = [
                item for item in evidence
                if item.competitor == competitor or (item.competitor is None and len(competitor_order) == 1)
            ]
            buckets, competitor_unmapped = self._capability_buckets_for_competitor(
                competitor,
                competitor_evidence,
                feature_taxonomy=feature_taxonomy,
            )
            competitor_capabilities[competitor] = buckets
            unmapped_signals.extend(competitor_unmapped)

        aggregate_by_area: dict[str, list[CapabilityBucket]] = defaultdict(list)
        for buckets in competitor_capabilities.values():
            for bucket in buckets:
                aggregate_by_area[bucket.capability_area].append(bucket)

        for area, buckets in aggregate_by_area.items():
            aggregate_buckets.append(
                CapabilityBucket(
                    competitor=None,
                    capability_area=area,
                    normalized_features=self._dedupe(
                        feature
                        for bucket in buckets
                        for feature in bucket.normalized_features
                    ),
                    evidence_ids=self._dedupe(
                        evidence_id
                        for bucket in buckets
                        for evidence_id in bucket.evidence_ids
                    ),
                    confidence=round(sum(bucket.confidence for bucket in buckets) / max(len(buckets), 1), 2),
                    insufficient_evidence=all(bucket.insufficient_evidence for bucket in buckets),
                    summary=f"Observed across {len(buckets)} competitor capability buckets.",
                    signals=[
                        signal
                        for bucket in buckets
                        for signal in bucket.signals
                    ][:8],
                )
            )

        return CapabilityMap(
            domain_pack=domain_pack,
            competitor_capabilities=competitor_capabilities,
            aggregate_capabilities=sorted(aggregate_buckets, key=lambda item: item.capability_area),
            unmapped_signals=unmapped_signals[:12],
            evidence_ids=self._ids(evidence),
        )

    def _capability_buckets_for_competitor(
        self,
        competitor: str,
        evidence: list[Evidence],
        *,
        feature_taxonomy: dict[str, tuple[str, ...]],
    ) -> tuple[list[CapabilityBucket], list[CapabilitySignal]]:
        signals_by_area: dict[str, list[CapabilitySignal]] = defaultdict(list)
        unmapped: list[CapabilitySignal] = []

        for item in evidence:
            text = self._evidence_text(item).lower()
            matched_area = False
            for area, keywords in feature_taxonomy.items():
                matched_keywords = [keyword for keyword in keywords if keyword.lower() in text]
                if not matched_keywords:
                    continue
                matched_area = True
                signals_by_area[area].append(
                    CapabilitySignal(
                        competitor=competitor,
                        capability_area=area,
                        normalized_feature=area,
                        evidence_ids=[item.evidence_id],
                        confidence=round(min(0.95, max(0.45, item.confidence)), 2),
                        insufficient_evidence=False,
                        matched_keywords=matched_keywords[:4],
                        support_summary=self._compact(self._evidence_text(item)),
                    )
                )
            if not matched_area:
                fallback_area = self._generic_capability_area(text)
                if fallback_area is None:
                    unmapped.append(
                        CapabilitySignal(
                            competitor=competitor,
                            capability_area="other",
                            normalized_feature="unmapped_signal",
                            evidence_ids=[item.evidence_id],
                            confidence=round(min(0.6, max(0.3, item.confidence)), 2),
                            insufficient_evidence=False,
                            matched_keywords=[],
                            support_summary=self._compact(self._evidence_text(item)),
                        )
                    )
                    continue
                signals_by_area[fallback_area].append(
                    CapabilitySignal(
                        competitor=competitor,
                        capability_area=fallback_area,
                        normalized_feature=fallback_area,
                        evidence_ids=[item.evidence_id],
                        confidence=round(min(0.7, max(0.35, item.confidence)), 2),
                        insufficient_evidence=False,
                        matched_keywords=[],
                        support_summary=self._compact(self._evidence_text(item)),
                    )
                )

        if not evidence and not signals_by_area:
            return (
                [
                    CapabilityBucket(
                        competitor=competitor,
                        capability_area="evidence_gap",
                        normalized_features=[],
                        evidence_ids=["insufficient_evidence"],
                        confidence=0.25,
                        insufficient_evidence=True,
                        summary="Relevant public evidence is insufficient for capability extraction.",
                        signals=[],
                    )
                ],
                [],
            )

        if unmapped:
            signals_by_area["other"].extend(unmapped)

        buckets: list[CapabilityBucket] = []
        for area, signals in signals_by_area.items():
            evidence_ids = self._dedupe(evidence_id for signal in signals for evidence_id in signal.evidence_ids)
            buckets.append(
                CapabilityBucket(
                    competitor=competitor,
                    capability_area=area,
                    normalized_features=self._dedupe(signal.normalized_feature for signal in signals),
                    evidence_ids=evidence_ids,
                    confidence=round(sum(signal.confidence for signal in signals) / max(len(signals), 1), 2),
                    insufficient_evidence=False,
                    summary=f"{competitor} shows evidence-backed signals for {area}.",
                    signals=signals[:8],
                )
            )
        return sorted(buckets, key=lambda item: item.capability_area), unmapped

    def _legacy_feature_tree_projection(self, capability_map: CapabilityMap) -> dict[str, list[str]]:
        projected: dict[str, list[str]] = {}
        for area_bucket in capability_map.aggregate_capabilities:
            labels = []
            for bucket in capability_map.competitor_capabilities.values():
                for competitor_bucket in bucket:
                    if competitor_bucket.capability_area != area_bucket.capability_area:
                        continue
                    labels.append(
                        f"{competitor_bucket.competitor}: {', '.join(competitor_bucket.normalized_features[:3]) or competitor_bucket.capability_area}"
                    )
            if labels:
                projected[area_bucket.capability_area] = labels[:4]
        return projected

    def _legacy_differentiators(self, capability_map: CapabilityMap) -> list[str]:
        differentiators = []
        for bucket in capability_map.aggregate_capabilities[:4]:
            if bucket.insufficient_evidence:
                continue
            differentiators.append(
                f"Evidence-backed capability area: {bucket.capability_area}"
            )
        return differentiators

    def _generic_capability_area(self, text: str) -> str | None:
        for area, keywords in FEATURE_KEYWORDS.items():
            if any(keyword.lower() in text for keyword in keywords):
                return area.lower()
        return None

    def _feature_hits(self, task, evidence: list[Evidence]) -> dict[str, list[Evidence]]:
        hits: dict[str, list[Evidence]] = defaultdict(list)
        resolved_domain_pack = resolve_domain_pack(task)
        feature_keywords = {
            **FEATURE_KEYWORDS,
            **{feature: list(keywords) for feature, keywords in resolved_domain_pack.feature_taxonomy.items()},
        }
        for item in evidence:
            text = self._evidence_text(item).lower()
            for feature, keywords in feature_keywords.items():
                if any(keyword.lower() in text for keyword in keywords):
                    hits[feature].append(item)
        return dict(hits)

    def _keyword_evidence(self, evidence: list[Evidence], keywords: list[str]) -> list[Evidence]:
        matched = []
        for item in evidence:
            text = f"{self._evidence_text(item)} {item.url or ''}".lower()
            if any(keyword.lower() in text for keyword in keywords):
                matched.append(item)
        return matched

    def _persona_hits(self, evidence: list[Evidence]) -> dict[str, list[Evidence]]:
        hits: dict[str, list[Evidence]] = defaultdict(list)
        for item in evidence:
            text = self._evidence_text(item).lower()
            for persona, keywords in PERSONA_KEYWORDS.items():
                if any(keyword.lower() in text for keyword in keywords):
                    hits[persona].append(item)
        return dict(hits)

    @staticmethod
    def _feature_labels(feature: str, evidence: list[Evidence]) -> list[str]:
        ids = ", ".join(item.evidence_id for item in evidence[:3])
        return [f"{feature} related evidence: {ids}"]

    @staticmethod
    def _strengths_from_features(feature_hits: dict[str, list[Evidence]]) -> list[str]:
        return [f"Public evidence mentions {feature} capability" for feature in list(feature_hits.keys())[:4]]

    @staticmethod
    def _pricing_notes(evidence: list[Evidence]) -> str:
        if not evidence:
            return "Evidence is insufficient for a confident pricing conclusion."
        return "Public evidence includes pricing or packaging signals; official pages should be used for final validation."

    def _pricing_tiers(self, evidence: list[Evidence]) -> list[str]:
        if not evidence:
            return ["Evidence is insufficient"]
        return [
            "free/trial signal"
            if any(word in self._evidence_text(item).lower() for word in ["free", "trial", "免费", "试用"])
            else "paid/enterprise signal"
            for item in evidence[:3]
        ]

    @staticmethod
    def _selected_dimensions(input_data: AnalystInput) -> list[str]:
        return [str(item).strip().lower() for item in input_data.selected_dimensions if str(item).strip()]

    @staticmethod
    def _count_swot_items(swot: SwotAnalysis) -> int:
        return len(swot.strengths) + len(swot.weaknesses) + len(swot.opportunities) + len(swot.threats)

    def _build_mock_swot(self, competitors: list[str], ids: list[str], selected_dimensions: list[str]) -> SwotAnalysis:
        dimensions = ", ".join(selected_dimensions[:3]) if selected_dimensions else "feature, pricing, persona"
        competitor_label = competitors[0] if competitors else None
        return SwotAnalysis(
            strengths=[
                SwotItem(
                    summary=f"Mock analysis highlights evidence traceability across {dimensions}.",
                    competitor=competitor_label,
                    evidence_ids=ids[:1],
                    confidence=0.55,
                )
            ],
            weaknesses=[
                SwotItem(
                    summary="Mock extraction still relies on simplified rules and should be validated with richer evidence.",
                    competitor=competitor_label,
                    evidence_ids=ids[:1],
                    confidence=0.45,
                )
            ],
            opportunities=[
                SwotItem(
                    summary=f"Planner-selected dimensions suggest deeper comparison opportunities around {dimensions}.",
                    competitor=competitor_label,
                    evidence_ids=ids[:1],
                    confidence=0.5,
                )
            ],
            threats=[
                SwotItem(
                    summary="Public-evidence gaps can still limit confident competitor differentiation.",
                    competitor=competitor_label,
                    evidence_ids=ids[:1],
                    confidence=0.45,
                )
            ],
        )

    def _build_evidence_swot(
        self,
        competitors: list[str],
        selected_dimensions: list[str],
        *,
        evidence_by_competitor: dict[str, list[Evidence]],
        competitor_analysis: dict[str, dict],
        aggregate_feature_hits: dict[str, list[Evidence]],
    ) -> SwotAnalysis:
        strengths: list[SwotItem] = []
        weaknesses: list[SwotItem] = []
        opportunities: list[SwotItem] = []
        threats: list[SwotItem] = []
        dimension_focus = set(selected_dimensions)

        for feature, feature_evidence in sorted(aggregate_feature_hits.items(), key=lambda item: len(item[1]), reverse=True)[:3]:
            feature_competitors = {item.competitor for item in feature_evidence if item.competitor}
            competitor = next(iter(feature_competitors)) if len(feature_competitors) == 1 else None
            strengths.append(
                SwotItem(
                    summary=f"Public evidence repeatedly mentions {feature} capability, making it a visible competitive strength.",
                    competitor=competitor,
                    evidence_ids=[item.evidence_id for item in feature_evidence[:3]] or ["insufficient_evidence"],
                    confidence=min(0.9, 0.55 + 0.08 * len(feature_evidence)),
                )
            )

        for competitor in competitors:
            records = evidence_by_competitor.get(competitor, [])
            analysis = competitor_analysis.get(competitor, {})
            record_ids = [item.evidence_id for item in records[:3]] or ["insufficient_evidence"]
            if not records or analysis.get("insufficient_evidence"):
                weaknesses.append(
                    SwotItem(
                        summary="Relevant public evidence is still too thin for a strong competitor-specific conclusion.",
                        competitor=competitor,
                        evidence_ids=record_ids,
                        confidence=0.35,
                    )
                )
                threats.append(
                    SwotItem(
                        summary="Thin evidence coverage increases the risk of over-indexing on a small set of public signals.",
                        competitor=competitor,
                        evidence_ids=record_ids,
                        confidence=0.35,
                    )
                )
                continue

            pricing_records = self._keyword_evidence(records, PRICING_KEYWORDS)
            feature_labels = analysis.get("features") or []
            if pricing_records and {"pricing", "positioning"} & dimension_focus:
                opportunities.append(
                    SwotItem(
                        summary="Pricing and packaging signals are visible enough to support a sharper positioning comparison in the next step.",
                        competitor=competitor,
                        evidence_ids=[item.evidence_id for item in pricing_records[:3]],
                        confidence=0.65,
                    )
                )
            if feature_labels and feature_labels[0] != "insufficient evidence":
                opportunities.append(
                    SwotItem(
                        summary=f"Observed signals around {', '.join(feature_labels[:2])} create room for more targeted feature differentiation.",
                        competitor=competitor,
                        evidence_ids=record_ids,
                        confidence=0.6,
                    )
                )
            weaknesses.append(
                SwotItem(
                    summary=(
                        "UX and user-feedback conclusions should stay conservative until more explicit pain-point evidence is collected."
                        if {"ux", "feedback", "prioritization"} & dimension_focus
                        else "Current public evidence still leaves some workflow and buyer-fit uncertainty."
                    ),
                    competitor=competitor,
                    evidence_ids=record_ids,
                    confidence=0.5,
                )
            )
            threats.append(
                SwotItem(
                    summary="Cross-competitor conclusions should remain guarded because available evidence may not cover the full product surface.",
                    competitor=competitor,
                    evidence_ids=record_ids,
                    confidence=0.5,
                )
            )

        fallback_competitor = competitors[0] if competitors else None
        if not strengths:
            strengths.append(
                SwotItem(
                    summary="Some relevant evidence exists, but not enough to isolate a durable strength yet.",
                    competitor=fallback_competitor,
                    evidence_ids=["insufficient_evidence"],
                    confidence=0.35,
                )
            )
        if not opportunities:
            opportunities.append(
                SwotItem(
                    summary="Additional official documentation and pricing pages would improve opportunity mapping.",
                    competitor=fallback_competitor,
                    evidence_ids=["insufficient_evidence"],
                    confidence=0.35,
                )
            )

        return SwotAnalysis(
            strengths=strengths[:4],
            weaknesses=weaknesses[:4],
            opportunities=opportunities[:4],
            threats=threats[:4],
        )

    def _refine_swot_for_rework(
        self,
        swot: SwotAnalysis,
        *,
        input_data: AnalystInput,
        evidence_by_competitor: dict[str, list[Evidence]],
    ) -> tuple[SwotAnalysis, dict]:
        if input_data.rework_context is None:
            return swot, {"applied": False, "issues_seen": 0, "adjustments": []}

        metadata = input_data.rework_context.metadata or {}
        issues = metadata.get("swot_issues", []) if isinstance(metadata.get("swot_issues", []), list) else []
        if not issues:
            return swot, {"applied": False, "issues_seen": 0, "adjustments": []}

        refined = swot.model_copy(deep=True)
        evidence_by_id = {item.evidence_id: item for item in input_data.evidence}
        adjustments: list[str] = []

        for issue in issues:
            quadrant = issue.get("quadrant")
            competitor = issue.get("competitor")
            error_type = issue.get("error_type")
            if quadrant not in {"strengths", "weaknesses", "opportunities", "threats"}:
                continue
            items = getattr(refined, quadrant)
            for index, item in enumerate(items):
                if competitor and item.competitor not in {competitor, None}:
                    continue
                supporting_records = [
                    evidence_by_id[evidence_id]
                    for evidence_id in item.evidence_ids
                    if evidence_id in evidence_by_id and evidence_by_id[evidence_id].relevance_level in {"high", "medium"}
                ]
                competitor_records = evidence_by_competitor.get(item.competitor or competitor or "", [])
                if error_type == "swot_missing_support":
                    fallback_ids = [record.evidence_id for record in competitor_records[:2]] or ["insufficient_evidence"]
                    items[index] = item.model_copy(
                        update={
                            "summary": "Evidence remains too thin for a strong SWOT conclusion after recheck.",
                            "evidence_ids": fallback_ids,
                            "confidence": 0.35,
                        }
                    )
                    adjustments.append(f"{quadrant}:{item.competitor or 'overall'} softened due to missing support")
                elif error_type == "swot_over_inference":
                    items[index] = item.model_copy(
                        update={
                            "summary": f"Conservative follow-up: {item.summary}",
                            "confidence": min(item.confidence, 0.45),
                        }
                    )
                    adjustments.append(f"{quadrant}:{item.competitor or 'overall'} confidence lowered")
                elif error_type == "swot_competitor_mismatch":
                    same_competitor_ids = [record.evidence_id for record in competitor_records[:3]] or ["insufficient_evidence"]
                    items[index] = item.model_copy(
                        update={
                            "evidence_ids": same_competitor_ids,
                            "confidence": 0.4 if same_competitor_ids == ["insufficient_evidence"] else min(item.confidence, 0.5),
                        }
                    )
                    adjustments.append(f"{quadrant}:{item.competitor or 'overall'} evidence rebound to same competitor")
                elif error_type == "swot_dimension_gap" and supporting_records:
                    items[index] = item.model_copy(update={"confidence": min(item.confidence, 0.55)})
                    adjustments.append(f"{quadrant}:{item.competitor or 'overall'} kept conservative for planner dimension gap")

        return refined, {
            "applied": bool(adjustments),
            "issues_seen": len(issues),
            "adjustments": adjustments,
            "rework_error_type": input_data.rework_context.error_type,
        }
