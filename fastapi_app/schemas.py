from datetime import datetime
from pydantic import BaseModel


# as like as DTOs 

class UserProfileOut(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    email: str
    bio: str | None = None

    model_config = {"from_attributes": True}


class UserPhotoOut(BaseModel):
    id: int
    photo_base64: str | None = None


class RTDSOut(BaseModel):
    symbol: str
    price: float | None
    bid: float | None
    ask: float | None
    day_volume: int | None
    source_ts: datetime | None
    ingested_at: datetime

    model_config = {"from_attributes": True}