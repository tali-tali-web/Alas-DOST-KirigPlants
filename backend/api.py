import configparser
import warnings
import numpy as np
import joblib
import asyncio
import selectors

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from datetime import datetime, UTC
from pydantic import BaseModel, Field

import postgresql
import processing


class SensorPacket(BaseModel):
    esp_chip_id: str = Field(min_length=12, max_length=12)
    duration: float = Field(ge=1)
    samples: list[int]

class SessionRequest(BaseModel):
    device_id: int
    label: str = Field(min_length=1, max_length=64)

class StopSessionRequest(BaseModel):
    device_id: int


router = FastAPI()

config = configparser.ConfigParser()
config.read("settings.conf")

router.mount(
    "/static",
    StaticFiles(directory="./backend/static"),
    name="static"
)

router.state.context = postgresql.Context(config)
router.state.templates = Jinja2Templates(directory="./backend/templates")


WINDOW_SIZE = 128
PREDICTION_WINDOWS = 4

CLASS_LABELS = {
    0: "Control",
    1: "Wind"
}

model = joblib.load("rf_model.joblib")
@router.post("/api/upload")
async def receive_data(
    request: Request,
    sensor_packet: SensorPacket,
    api_key: str = Header()
):
    context = request.app.state.context
    config = context.config

    if api_key != config["api"]["api_key"] and config["api"]["api_key"] is not None:
        print(f"[-] alert: unauthenticated device {sensor_packet.esp_chip_id}...")
        return {"received": None}

    expected = float(config["processing"]["samples_per_second"])
    actual = len(sensor_packet.samples) / sensor_packet.duration

    if abs(actual - expected) > 1:
        warnings.warn(
            "Sensor packet mismatch with expected samples per second",
            RuntimeWarning
        )

    received_at = datetime.now(UTC)
    samples = np.asarray(sensor_packet.samples, dtype=np.int32)

    postgresql.store_data(context, sensor_packet.esp_chip_id, samples)

    return {"received": received_at}


@router.get("/api/download")
async def request_data(request: Request, esp_chip_id: str, limit: int = 5000):
    context = request.app.state.context
    samples = postgresql.request_data(context, esp_chip_id, limit)

    if not samples:
        return []

    return [
        {"value": value, "timestamp": timestamp}
        for value, timestamp in samples
    ]


@router.get("/api/devices")
async def request_devices(request: Request):
    context = request.app.state.context
    devices = postgresql.list_devices(context)

    return [
        {
            "id": row[0],
            "device_id": row[0],
            "created_at": row[1].isoformat(),
            "esp_chip_id": row[2],
            "active_session_id": context.active_sessions.get(row[0])
        }
        for row in devices
    ]


@router.post("/api/session/start")
async def start_recording(request: Request, session_request: SessionRequest):
    context = request.app.state.context

    session_id = postgresql.start_session(
        context=context,
        device_id=session_request.device_id,
        label=session_request.label
    )

    if not session_id:
        raise HTTPException(
            status_code=409,
            detail="Device already has an active session"
        )

    return {
        "device_id": session_request.device_id,
        "session_id": session_id,
        "label": session_request.label
    }


@router.post("/api/session/stop")
async def stop_recording(request: Request, session_request: StopSessionRequest):
    context = request.app.state.context

    session_id = postgresql.stop_session(
        context=context,
        device_id=session_request.device_id
    )

    if not session_id:
        raise HTTPException(
            status_code=404,
            detail="Device does not have an active session"
        )

    return {
        "device_id": session_request.device_id,
        "session_id": session_id
    }


@router.get("/api/predict")
async def predict(request: Request, esp_chip_id: str):
    context = request.app.state.context

    requested_samples = WINDOW_SIZE * PREDICTION_WINDOWS

    samples = postgresql.request_data(
        context,
        esp_chip_id,
        requested_samples
    )

    if not samples:
        return {
            "prediction": None,
            "label": "No active session",
            "confidence": None,
            "sample_count": 0,
            "window_size": WINDOW_SIZE
        }

    available_windows = len(samples) // WINDOW_SIZE

    if available_windows == 0:
        return {
            "prediction": None,
            "label": "Collecting",
            "confidence": None,
            "sample_count": len(samples),
            "window_size": WINDOW_SIZE
        }

    samples = list(reversed(samples[:available_windows * WINDOW_SIZE]))
    values = [s[0] for s in samples]

    feature_vectors = []

    for start in range(0, len(values), WINDOW_SIZE):
        window = values[start:start + WINDOW_SIZE]
        processed = processing.preprocess_window(window)
        feature_vectors.append(processed)

    feature_vectors = np.asarray(feature_vectors, dtype=np.float32)

    probabilities = np.asarray(model.predict_proba(feature_vectors), dtype=np.float32)
    avg_prob = probabilities.mean(axis=0)

    prediction, confidence, smoothed, instant = processing.smooth_prediction(
        esp_chip_id,
        avg_prob
    )

    return {
        "prediction": prediction,
        "label": CLASS_LABELS.get(prediction, str(prediction)),
        "confidence": confidence,
        "sample_count": len(samples),
        "window_size": WINDOW_SIZE,
        "windows_used": available_windows,
        "class_probabilities": {
            CLASS_LABELS.get(int(label), str(label)): float(prob)
            for label, prob in zip(model.classes_, avg_prob)
        },
        "instant_wind_probability": instant,
        "smoothed_wind_probability": smoothed,
        "raw_mean": float(np.mean(values)),
        "raw_std": float(np.std(values))
    }

@router.get("/dashboard")
async def live_dashboard(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="/live.html"
    )

@router.get("/")
async def redirect_dashboard():
    return RedirectResponse(url="/dashboard")
