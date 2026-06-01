import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR / "backend" / ".env")


@dataclass(frozen=True)
class SurveyLLMConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    temperature: float
    timeout_seconds: float


def get_survey_llm_config() -> SurveyLLMConfig:
    base_url = os.getenv("SURVEY_LLM_BASE_URL") or os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1"
    return SurveyLLMConfig(
        provider=os.getenv("SURVEY_LLM_PROVIDER") or os.getenv("LLM_PROVIDER", "openai_compatible"),
        api_key=os.getenv("SURVEY_LLM_API_KEY") or os.getenv("LLM_API_KEY", ""),
        base_url=base_url.strip().rstrip("/"),
        model=os.getenv("SURVEY_LLM_MODEL") or os.getenv("LLM_MODEL", "gpt-4o-mini"),
        temperature=_float_env("SURVEY_LLM_TEMPERATURE", 0.3),
        timeout_seconds=min(_float_env("SURVEY_LLM_TIMEOUT_SECONDS", 12.0), 12.0),
    )


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default
