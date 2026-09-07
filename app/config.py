import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    provider: str = field(default_factory=lambda: os.getenv("AGENT_PROVIDER", "local"))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    max_steps: int = int(os.getenv("MAX_STEPS", "6"))
    runs_dir: str = field(default_factory=lambda: os.getenv("RUNS_DIR", "./runs"))
    crm_path: str = field(default_factory=lambda: os.getenv("CRM_PATH", "./data/crm.json"))
    calendar_path: str = field(default_factory=lambda: os.getenv("CALENDAR_PATH", "./data/calendar.json"))


settings = Settings()