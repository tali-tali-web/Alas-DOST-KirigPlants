from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import RedirectResponse

from pydantic import BaseModel

import src.processing, postgresql


router = FastAPI()

#router.add_middleware(HTTPSRedirectMiddleware)

API_KEY = "something-stupid-over-here"  


class SensorData(BaseModel):
    ESP_ID : str = Field(min_length=12, max_length=12)
    start_timestamp : int
    end_timestamp : int
    data : list[int] 


@router.post("/api/data")
async def receive_data(data : SensorData, x_api_key : str = Header(None)):

    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    processed = await processing.parser.parse_data(data) 
    await postgresql.store_data(processed)

    return {"status": "ok"}

@router.get("/")
async def request_dashboard_redirect():
    return RedirectResponse(url="/dashboard")

@router.get("/dashboard")
async def request_dashboard():
    return{"tree" : "yes"}


