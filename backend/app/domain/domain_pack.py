from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.models import DomainPackReference, PlannerExtractedContext, Task


@dataclass(frozen=True)
class DomainPackSpec:
    domain_pack_id: str
    display_name: str
    category_key: str | None = None
    match_terms: tuple[str, ...] = ()
    competitor_candidates: tuple[tuple[str, str, float], ...] = ()
    dimension_keywords: dict[str, tuple[str, ...]] = field(default_factory=dict)
    category_query_templates: tuple[str, ...] = ()
    competitor_query_templates: tuple[str, ...] = ()
    feature_taxonomy: dict[str, tuple[str, ...]] = field(default_factory=dict)
    source_preferences: tuple[str, ...] = ()
    survey_theme_hints: tuple[str, ...] = ()


GENERIC_PACK = DomainPackSpec(
    domain_pack_id="generic_competitive",
    display_name="Generic Competitive Analysis",
    feature_taxonomy={
        "workflow": ("workflow", "process", "automation"),
        "integration": ("integration", "api", "platform"),
        "analytics": ("analytics", "reporting", "dashboard"),
        "security": ("security", "compliance", "permission"),
    },
    source_preferences=("official", "documentation", "media"),
    survey_theme_hints=("pain points", "switching reasons", "feature importance"),
)

SMARTPHONE_PACK = DomainPackSpec(
    domain_pack_id="smartphone_flagship",
    display_name="Smartphone Flagship Benchmark",
    category_key="smartphone",
    match_terms=("smartphone", "phone", "flagship", "mobile", "手机", "旗舰"),
    competitor_candidates=(
        ("Apple iPhone", "Common premium smartphone benchmark.", 0.9),
        ("Samsung Galaxy", "Common premium Android benchmark.", 0.88),
        ("Xiaomi", "Major smartphone vendor with flagship line.", 0.84),
        ("Huawei", "Major smartphone vendor with flagship line.", 0.84),
    ),
    dimension_keywords={
        "positioning": ("flagship positioning", "premium segment", "brand differentiation"),
        "feature": ("battery life", "charging speed", "camera performance", "os experience"),
        "pricing": ("retail price", "flagship pricing", "premium pricing", "model variants"),
        "persona": ("premium buyers", "switchers", "mobile power users", "use cases"),
        "ux": ("daily use", "os experience", "usability", "pain points"),
        "feedback": ("user feedback", "complaints", "reviews", "pain points"),
        "prioritization": ("improvement priorities", "purchase drivers", "feature importance"),
        "risk": ("ecosystem risk", "brand risk", "trade-offs"),
        "hypothesis": ("validation", "assumption", "user expectations"),
        "market": ("flagship market", "premium segment", "buyer trends"),
    },
    category_query_templates=(
        "{category} benchmark competitors official pricing features",
        "{category} buyer reviews feature comparison",
        "{category} battery camera charging performance reviews",
    ),
    competitor_query_templates=(
        "{competitor} official {industry}",
        "{competitor} pricing official",
        "{competitor} features documentation",
        "{competitor} battery camera charging reviews",
    ),
    feature_taxonomy={
        "battery": ("battery", "battery life", "续航", "charging", "快充"),
        "camera": ("camera", "imaging", "影像", "photo", "video"),
        "performance": ("performance", "chip", "gaming", "散热"),
        "os": ("os", "system", "ui", "experience", "系统"),
    },
    source_preferences=("official", "media", "review"),
    survey_theme_hints=("battery complaints", "camera expectations", "switching intent"),
)

CRM_PACK = DomainPackSpec(
    domain_pack_id="crm_b2b",
    display_name="CRM Benchmark",
    category_key="crm",
    match_terms=("crm", "salesforce", "hubspot", "pipeline", "sales ops"),
    competitor_candidates=(
        ("Salesforce", "Category leader for CRM benchmarking.", 0.92),
        ("HubSpot", "Common SMB and mid-market CRM benchmark.", 0.9),
        ("Zoho CRM", "Common cost-conscious CRM benchmark.", 0.82),
        ("Pipedrive", "Common pipeline-first CRM benchmark.", 0.8),
    ),
    dimension_keywords={
        "positioning": ("crm positioning", "segment fit", "buyer messaging"),
        "feature": ("workflow automation", "pipeline", "integrations", "reporting"),
        "pricing": ("pricing", "seat pricing", "plans", "enterprise pricing"),
        "persona": ("sales teams", "revenue operations", "crm buyers", "use cases"),
        "ux": ("usability", "adoption friction", "workflow pain points"),
        "feedback": ("user feedback", "pain points", "reviews", "complaints"),
        "prioritization": ("feature requests", "buyer priorities", "improvement priorities"),
        "risk": ("switching risk", "implementation risk", "lock-in"),
        "hypothesis": ("validation", "assumption", "adoption blockers"),
        "market": ("crm market", "segment trends", "buyer expectations"),
    },
    category_query_templates=(
        "{category} benchmark competitors official pricing features",
        "{category} buyer reviews feature comparison",
        "{category} workflow automation pipeline integrations pricing",
    ),
    competitor_query_templates=(
        "{competitor} official {industry}",
        "{competitor} pricing official",
        "{competitor} features documentation",
        "{competitor} workflow automation integrations",
    ),
    feature_taxonomy={
        "automation": ("automation", "workflow", "sequence", "approval"),
        "pipeline": ("pipeline", "deal", "opportunity", "forecast"),
        "integration": ("integration", "ecosystem", "api", "sync"),
        "reporting": ("reporting", "analytics", "dashboard", "attribution"),
    },
    source_preferences=("official", "documentation", "review"),
    survey_theme_hints=("adoption friction", "admin pain points", "switching barriers"),
)

AI_NOTE_PACK = DomainPackSpec(
    domain_pack_id="ai_note_taking",
    display_name="AI Note-Taking Tools",
    category_key="ai_note_taking",
    match_terms=("note-taking", "note taking", "meeting notes", "notes", "笔记"),
    competitor_candidates=(
        ("Notion AI", "Common AI workspace benchmark.", 0.9),
        ("Obsidian", "Common personal knowledge benchmark.", 0.82),
        ("Otter.ai", "Common meeting transcript benchmark.", 0.86),
        ("Mem", "Common AI note workflow benchmark.", 0.78),
    ),
    dimension_keywords={
        "positioning": ("category positioning", "workspace differentiation", "use case fit"),
        "feature": ("meeting notes", "ai search", "knowledge capture", "organization"),
        "pricing": ("pricing", "subscription", "team plan", "free tier"),
        "persona": ("knowledge workers", "teams", "students", "meeting-heavy users"),
        "ux": ("usability", "capture workflow", "recall workflow", "pain points"),
        "feedback": ("user feedback", "reviews", "complaints", "adoption pain points"),
        "prioritization": ("buyer priorities", "workflow importance", "improvement priorities"),
        "risk": ("privacy risk", "workflow switching risk", "lock-in"),
        "hypothesis": ("validation", "assumption", "user expectations"),
        "market": ("category trends", "buyer expectations", "competitive landscape"),
    },
    category_query_templates=(
        "{category} benchmark competitors official pricing features",
        "{category} buyer reviews feature comparison",
        "{category} ai notes meeting capture search workflow reviews",
    ),
    competitor_query_templates=(
        "{competitor} official {industry}",
        "{competitor} pricing official",
        "{competitor} features documentation",
        "{competitor} meeting notes workflow reviews",
    ),
    feature_taxonomy={
        "capture": ("capture", "recording", "transcript", "meeting notes"),
        "search": ("search", "recall", "retrieval", "knowledge"),
        "organization": ("organization", "workspace", "tag", "folder"),
        "collaboration": ("collaboration", "sharing", "team", "comment"),
    },
    source_preferences=("official", "documentation", "review"),
    survey_theme_hints=("capture friction", "search quality", "workflow lock-in"),
)

PACKS = (SMARTPHONE_PACK, CRM_PACK, AI_NOTE_PACK)


def resolve_domain_pack(task: Task, extracted: PlannerExtractedContext | None = None) -> DomainPackSpec:
    text = " ".join(
        filter(
            None,
            (
                task.product_name,
                task.industry,
                task.region,
                " ".join(task.competitors),
                extracted.industry if extracted else None,
                extracted.domain if extracted else None,
                " ".join(extracted.analysis_focus_points) if extracted else None,
            ),
        )
    ).lower()
    for pack in PACKS:
        if any(term in text for term in pack.match_terms):
            return pack
    return GENERIC_PACK


def domain_pack_reference(
    pack: DomainPackSpec,
    *,
    industry_label: str | None,
    source: str = "resolver",
    metadata: dict[str, object] | None = None,
) -> DomainPackReference:
    return DomainPackReference(
        domain_pack_id=pack.domain_pack_id,
        display_name=pack.display_name,
        category_key=pack.category_key,
        source=source,
        industry_label=industry_label,
        supported_dimensions=list(pack.dimension_keywords.keys()),
        feature_taxonomy_keys=list(pack.feature_taxonomy.keys()),
        source_preferences=list(pack.source_preferences),
        survey_theme_hints=list(pack.survey_theme_hints),
        metadata=dict(metadata or {}),
    )
