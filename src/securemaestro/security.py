import re
from pydantic import BaseModel, ValidationError, field_validator

YOUTUBE_RX = re.compile(
    r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$", re.IGNORECASE
)

class LoopRequest(BaseModel):
    url: str
    start_sec: float
    end_sec: float
    speed: float
    repeats: int
    max_full_length_sec: int = 1200  # 20 min cap default

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not YOUTUBE_RX.match(v.strip()):
            raise ValueError("Only YouTube/youtu.be URLs are allowed for MVP.")
        return v

    @field_validator("start_sec", "end_sec")
    @classmethod
    def validate_times(cls, v: float) -> float:
        if v < 0 or v > 6 * 3600:
            raise ValueError("Time must be within 0..21600 seconds.")
        return v

    @field_validator("speed")
    @classmethod
    def validate_speed(cls, v: float) -> float:
        if v <= 0.0 or v > 2.0:
            raise ValueError("Speed must be in (0, 2.0].")
        return v

    @field_validator("repeats")
    @classmethod
    def validate_repeats(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("Repeats must be 1..100.")
        return v

def validate_loop_request(**kwargs) -> LoopRequest:
    try:
        return LoopRequest(**kwargs)
    except ValidationError as e:
        raise ValueError(e.errors())