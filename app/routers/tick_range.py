import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services import tick_range as tick_range_service

router = APIRouter(prefix="/v1/history/tick-range", tags=["tick-range"])


class TickRangeRequest(BaseModel):
    instrument: str
    date_from: datetime
    date_to: datetime
    min_price: Decimal
    max_price: Decimal
    initial_bid: Decimal
    volatility_sigma: float
    spread_mean: float
    spread_stdev: float
    time_unit_seconds: float
    mean_ticks: float
    dispersion: float
    min_ticks: int
    max_ticks: int


@router.get("/{tick_range_id}/data")
async def get_data(tick_range_id: uuid.UUID):
    status = await tick_range_service.get_status(tick_range_id)
    return JSONResponse(status_code=409, content={"status": status})


@router.post("", status_code=202)
async def request_tick_range(request: TickRangeRequest):
    tick_range_id = await tick_range_service.request_tick_range(request.model_dump())
    return {"tick_range_id": str(tick_range_id), "status": "REQUESTED"}
