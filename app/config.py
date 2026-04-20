"""
Centralised settings, loaded from environment variables / .env file.
Using pydantic-settings so typos and missing values fail loudly at startup.
"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    port: int = Field(default=8000)

    # WhatsApp
    whatsapp_phone_number_id: str = Field(default="")
    whatsapp_business_account_id: str = Field(default="")
    whatsapp_access_token: str = Field(default="")
    whatsapp_webhook_verify_token: str = Field(default="change-me")
    whatsapp_app_secret: str = Field(default="")

    # Supabase / DB
    supabase_db_url: str = Field(default="")
    supabase_url: str = Field(default="")
    supabase_service_role_key: str = Field(default="")

    # Anthropic
    anthropic_api_key: str = Field(default="")
    anthropic_model: str = Field(default="claude-haiku-4-5-20251001")

    # OpenAI
    openai_api_key: str = Field(default="")
    openai_whisper_model: str = Field(default="whisper-1")
    fallback_openai_model: str = Field(default="gpt-4o-mini")

    # Business
    default_timezone: str = Field(default="Asia/Karachi")
    daily_summary_hour: int = Field(default=21)
    max_voice_notes_per_day: int = Field(default=200)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def assert_ready_for_runtime(self) -> list[str]:
        """Returns a list of missing critical settings; empty = ready."""
        missing = []
        if not self.whatsapp_access_token:
            missing.append("WHATSAPP_ACCESS_TOKEN")
        if not self.whatsapp_phone_number_id:
            missing.append("WHATSAPP_PHONE_NUMBER_ID")
        if not self.supabase_db_url or "YOUR-PROJECT" in self.supabase_db_url:
            missing.append("SUPABASE_DB_URL")
        if not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY (for voice notes)")
        return missing


@lru_cache
def get_settings() -> Settings:
    return Settings()
