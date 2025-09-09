from datetime import datetime

from pydantic import BaseModel

from api.services.configuration.registry import (
    LLMConfig,
    STTConfig,
    TTSConfig,
)


class UserConfiguration(BaseModel):
    llm: LLMConfig | None = None
    stt: STTConfig | None = None
    tts: TTSConfig | None = None
    test_phone_number: str | None = None
    timezone: str | None = None
    last_validated_at: datetime | None = None
