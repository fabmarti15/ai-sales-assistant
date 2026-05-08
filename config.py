"""
Config - centralised configuration loader.
Reads from environment variables with sensible defaults.
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_max_tokens: int = 200
    openai_temperature: float = 0.7

    # CRM
    crm_api_key: str = ""
    crm_provider: str = "hubspot"
    crm_base_url: str = "https://api.hubapi.com"
    crm_timeout: int = 15

    # Scoring
    scoring_hot_threshold: float = 70.0
    scoring_warm_threshold: float = 40.0
    scoring_batch_size: int = 100

    # Outreach
    outreach_daily_limit: int = 50
    outreach_dry_run: bool = False
    outreach_default_tone: str = "professional"

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"

    @classmethod
    def load(cls) -> "Config":
        return cls(
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            openai_max_tokens=int(os.environ.get("OPENAI_MAX_TOKENS", "200")),
            openai_temperature=float(os.environ.get("OPENAI_TEMPERATURE", "0.7")),
            crm_api_key=os.environ.get("CRM_API_KEY", ""),
            crm_provider=os.environ.get("CRM_PROVIDER", "hubspot"),
            crm_base_url=os.environ.get("CRM_BASE_URL", "https://api.hubapi.com"),
            crm_timeout=int(os.environ.get("CRM_TIMEOUT", "15")),
            scoring_hot_threshold=float(os.environ.get("SCORING_HOT_THRESHOLD", "70")),
            scoring_warm_threshold=float(os.environ.get("SCORING_WARM_THRESHOLD", "40")),
            scoring_batch_size=int(os.environ.get("SCORING_BATCH_SIZE", "100")),
            outreach_daily_limit=int(os.environ.get("OUTREACH_DAILY_LIMIT", "50")),
            outreach_dry_run=os.environ.get("OUTREACH_DRY_RUN", "false").lower() == "true",
            outreach_default_tone=os.environ.get("OUTREACH_TONE", "professional"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )

    def validate(self) -> None:
        errors = []
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required")
        if not self.crm_api_key:
            errors.append("CRM_API_KEY is required")
        if self.scoring_hot_threshold <= self.scoring_warm_threshold:
            errors.append("HOT threshold must be greater than WARM threshold")
        if errors:
            raise ValueError("Config validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    def __repr__(self) -> str:
        return (
            f"Config(model={self.openai_model}, crm={self.crm_provider}, "
            f"hot>={self.scoring_hot_threshold}, warm>={self.scoring_warm_threshold})"
        )
