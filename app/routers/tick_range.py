import uuid


from decimal import Decimal
from typing import Self

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from pydantic import AwareDatetime, BaseModel, Field, model_validator


from app.services import tick_range as tick_range_service
from app.services import tick_storage

router = APIRouter(prefix="/v1/history/tick-range", tags=["tick-range"])



INT32_MAX = 2_147_483_647
PRICE = {"max_digits": 18, "decimal_places": 8}  # NUMERIC(18,8)


class TickRangeRequest(BaseModel):
    """Mirrors the tick_range CHECK constraints and column limits, so that a bad
    request is a 422 here and never a database error."""

    instrument: str = Field(min_length=1, max_length=20)
    date_from: AwareDatetime
    date_to: AwareDatetime
    min_price: Decimal = Field(gt=0, **PRICE)
    max_price: Decimal = Field(**PRICE)
    initial_bid: Decimal = Field(**PRICE)
    volatility_sigma: float = Field(ge=0, allow_inf_nan=False)
    spread_mean: float = Field(ge=0, allow_inf_nan=False)
    spread_stdev: float = Field(ge=0, allow_inf_nan=False)
    time_unit_seconds: float = Field(gt=0, allow_inf_nan=False)
    mean_ticks: float = Field(gt=0, allow_inf_nan=False)
    dispersion: float = Field(gt=0, allow_inf_nan=False)
    min_ticks: int = Field(ge=0, le=INT32_MAX)
    max_ticks: int = Field(ge=1, le=INT32_MAX)


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
        if not self.min_ticks <= self.mean_ticks <= self.max_ticks:
            raise ValueError("mean_ticks must be between min_ticks and max_ticks")

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
