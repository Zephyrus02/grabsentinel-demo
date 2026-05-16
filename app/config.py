from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    SESSION_SECRET_KEY: str

    RESEND_API_KEY: str
    RESEND_FROM_EMAIL: str = "onboarding@resend.dev"

    OTP_LENGTH: int = 6
    OTP_EXPIRE_MINUTES: int = 10


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
