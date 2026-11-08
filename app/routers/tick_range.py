import uuid
from datetime import datetime
from decimal import Decimal
from typing import Self

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from app.services import tick_range as tick_range_service
from app.services import tick_storage

router = APIRouter(prefix="/v1/history/tick-range", tags=["tick-range"])


class TickRangeRequest(BaseModel):
    instrument: str = Field(min_length=1)
    date_from: datetime
    date_to: datetime
    min_price: Decimal = Field(gt=0)
    max_price: Decimal
    initial_bid: Decimal
    volatility_sigma: float = Field(ge=0)
    spread_mean: float = Field(ge=0)
    spread_stdev: float = Field(ge=0)
    time_unit_seconds: float = Field(gt=0)
    mean_ticks: float = Field(gt=0)
    dispersion: float = Field(gt=0)
    min_ticks: int = Field(ge=0)
    max_ticks: int

    @model_validator(mode="after")
    def check_ranges(self) -> Self:
        if self.date_from >= self.date_to:
            raise ValueError("date_from must be before date_to")
        if self.min_price >= self.max_price:
            raise ValueError("min_price must be below max_price")
        if not self.min_price <= self.initial_bid <= self.max_price:
            raise ValueError("initial_bid must be between min_price and max_price")
        if self.min_ticks > self.max_ticks:
            raise ValueError("min_ticks must not be above max_ticks")
        return self


@router.get("/{tick_range_id}/data")
async def get_data(tick_range_id: uuid.UUID):
    tick_range = await tick_range_service.get_tick_range(tick_range_id)
    if tick_range is None:
        raise HTTPException(status_code=404, detail="Tick range not found")
    if tick_range["status"] != "PROCESSED":
        return JSONResponse(status_code=409, content={"status": tick_range["status"]})
    ticks = tick_storage.read_ticks(tick_range["storage_bucket"], tick_range["storage_prefix"])
    return {
        "tick_range_id": str(tick_range_id),
        "records_produced": tick_range["records_produced"],
        "ticks": ticks,
    }


@router.post("", status_code=202)
async def request_tick_range(request: TickRangeRequest):
    tick_range_id = await tick_range_service.request_tick_range(request.model_dump())
    return {"tick_range_id": str(tick_range_id), "status": "REQUESTED"}
