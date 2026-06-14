from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import RedirectResponse

from pydantic import BaseModel, Field
from datetime import datetime, UTC


router = FastAPI()

#router.add_middleware(HTTPSRedirectMiddleware)

API_KEY = "something-stupid-over-here"  

class SensorData(BaseModel):
    device_id : str = Field(min_length=12, max_length=12)
    duration : float = Field(ge=2.0)
    received_at : str
    raw_adc : list[int] 


from processing import parser
from api import postgresql


@router.post("/api/data")
async def receive_data(data : SensorData, x_api_key : str = Header(None)):

    data.received_at = datetime.now(UTC)
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    processed = await processing.parser.parse_data(data) 
    await postgresql.store_sensor_data(processed)

    return {"status": "recieved", "recieved_at" : data.recieved_at}

@router.get("/")
async def request_dashboard_redirect():
    return RedirectResponse(url="/dashboard")

@router.get("/dashboard")
async def request_dashboard():
    return{"tree" : "yes"}


