from pydantic import BaseModel, field_validator


class SubtitleResponse(BaseModel):
    id: int
    material_id: int
    seq: int
    start_time: float
    end_time: float
    text: str
    is_verified: bool

    model_config = {"from_attributes": True}


class SubtitleUpdate(BaseModel):
    id: int
    seq: int
    start_time: float
    end_time: float
    text: str
    is_verified: bool

    @field_validator("start_time", "end_time")
    @classmethod
    def round_time(cls, v: float) -> float:
        return round(v, 3)

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: float, info) -> float:
        start = info.data.get("start_time")
        if start is not None and v <= start:
            raise ValueError("end_time must be greater than start_time")
        return v

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text cannot be empty")
        return v.strip()


class SubtitleBatchUpdate(BaseModel):
    subtitles: list[SubtitleUpdate]


class SubtitleListResponse(BaseModel):
    material_id: int
    subtitles: list[SubtitleResponse]
    total: int
    verified_count: int