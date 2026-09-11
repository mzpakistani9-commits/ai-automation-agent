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
    outbox_path: str = field(default_factory=lambda: os.getenv("OUTBOX_PATH", "./data/outbox.json"))
    slack_webhook_url: str = field(default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL", ""))
    resend_api_key: str = field(default_factory=lambda: os.getenv("RESEND_API_KEY", ""))
    resend_from: str = field(default_factory=lambda: os.getenv("RESEND_FROM", "agent@demo.example.com"))
    slack_outbox_path: str = field(default_factory=lambda: os.getenv("SLACK_OUTBOX_PATH", "./data/slack_outbox.json"))
    email_outbox_path: str = field(default_factory=lambda: os.getenv("EMAIL_OUTBOX_PATH", "./data/email_outbox.json"))


settings = Settings()