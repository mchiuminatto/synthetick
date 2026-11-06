from fastapi import FastAPI

from app.routers import tick_range

app = FastAPI()
app.include_router(tick_range.router)
