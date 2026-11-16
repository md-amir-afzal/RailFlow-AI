from pydantic import BaseModel, Field
from typing import Literal

class TrainCreate(BaseModel):
    id: str = Field(min_length=2, max_length=10)
    name: str = Field(min_length=2, max_length=100)
    category: Literal['Express','Superfast','Passenger','Local','Freight','Special'] = 'Express'
    origin: str
    destination: str
    route: list[str] = Field(min_length=2)
    priority: int = Field(default=3, ge=1, le=5)
    scheduled_departure: str
    delay_min: int = Field(default=0, ge=0, le=1440)
    speed_kmph: float = Field(default=80, gt=0, le=200)

class ScenarioRequest(BaseModel):
    scenario: Literal['normal','heavy_traffic','junction_delay','single_track','platform_block','maintenance'] = 'heavy_traffic'
    seed: int = 42
    intensity: int = Field(default=30, ge=0, le=180)

class OptimizeRequest(BaseModel):
    headway_min: int = Field(default=8, ge=1, le=60)
    horizon_hours: int = Field(default=24, ge=1, le=168)

class DelayFeedback(BaseModel):
    train_id: str = Field(min_length=2, max_length=10)
    actual_delay_min: float = Field(ge=0, le=1440)
    source: str = Field(default="operator_verified", min_length=3, max_length=80)
