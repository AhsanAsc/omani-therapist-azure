from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    # Azure Speech
    AZURE_SPEECH_KEY: str = Field(..., env="AZURE_SPEECH_KEY")
    AZURE_SPEECH_REGION: str = Field("uaenorth", env="AZURE_SPEECH_REGION")
    AZURE_SPEECH_ENDPOINT: str = Field("", env="AZURE_SPEECH_ENDPOINT")
    VOICE_AR: str = Field("ar-OM-AyshaNeural", env="VOICE_AR")
    VOICE_EN: str = Field("en-US-JennyNeural", env="VOICE_EN")

    # OpenAI
    OPENAI_API_KEY: str = Field("", env="OPENAI_API_KEY")
    OPENAI_MODEL: str = Field("gpt-4o-mini", env="OPENAI_MODEL")

    # Security & ops
    SECURE_MODE: bool = Field(True, env="SECURE_MODE")
    REDACT_LOGS: bool = Field(True, env="REDACT_LOGS")
    WS_PING_SECS: int = Field(25, env="WS_PING_SECS")
    REQUEST_TIMEOUT_SECS: int = Field(30, env="REQUEST_TIMEOUT_SECS")

    # Behavior knobs
    MAX_TOKENS: int = Field(180, env="MAX_TOKENS")
    TEMP: float = Field(0.4, env="TEMP")

    # pydantic-settings v2 config
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

@lru_cache()
def get_settings() -> Settings:
    return Settings()
