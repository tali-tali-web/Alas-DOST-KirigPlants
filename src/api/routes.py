from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import RedirectResponse

from pydantic import BaseModel, Field
from datetime import datetime, timedelta, UTC

import time, asyncio

router = FastAPI()

API_KEY = None  

class SensorData(BaseModel):
    esp_chip_id : str = Field(min_length=12, max_length=12)
    duration    : float = Field(ge=2.0)
    data_batch  : list[int] 

from processing import funnel
from api import postgresql


@router.post("/api/data")
async def receive_data(sensor_data : SensorData, x_api_key : str = Header()):

    if x_api_key != API_KEY and API_KEY != None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    received_at = datetime.now(UTC)
    return_values = []

    next_time = time.monotonic()
    for i, value in enumerate(sensor_data.data_batch):

        return_values.append(await funnel.iterate(sensor_data.esp_chip_id, value, True))

        next_time += 1 / funnel.sps
        sleep_duration = next_time - time.monotonic()

        if sleep_duration > 0:
            await asyncio.sleep(sleep_duration)


    await postgresql.store_data(sensor_data.esp_chip_id, return_values)
    return {"status": "received", "completed_at" : datetime.now(UTC), "received_at" : received_at}

@router.get("/")
async def request_dashboard_redirect():
    return RedirectResponse(url="/dashboard")

@router.get("/dashboard")
async def request_dashboard():
    return{"tree" : "yes"}


