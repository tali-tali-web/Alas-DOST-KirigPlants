from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import RedirectResponse

from pydantic import BaseModel, Field
from datetime import datetime, timedelta, UTC

router = FastAPI()

API_KEY = None  

class SensorData(BaseModel):
    esp_chip_id : str = Field(min_length=12, max_length=12)
    duration : float = Field(ge=2.0)
    received_at : str
    raw_adc : list[int] 

from processing import funnel
from api import postgresql


@router.post("/api/data")
async def receive_data(sensor_data : SensorData, x_api_key : str = Header()):

    if x_api_key != API_KEY and API_KEY != None:
        raise HTTPException(status_code=401, detail="Invalid API key")


    timestep = 1 / (len(sensor_data.raw_adc) - 1)
    sensor_data.received_at = datetime.now(UTC)
    for value in sensor_data:

        timestamp = sensor_data.received_at + timedelta(seconds = i * timestep)
        returned_value = funnel.processor.iterate(sensor_data.esp_chip_id, timestamp, value)
    
    return {"status": "received", "received_at" : data.received_at}

@router.get("/")
async def request_dashboard_redirect():
    return RedirectResponse(url="/dashboard")

@router.get("/dashboard")
async def request_dashboard():
    return{"tree" : "yes"}


