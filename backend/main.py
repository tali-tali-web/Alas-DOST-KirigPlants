import configparser, asyncio, uvicorn, warnings, numpy, threading, joblib
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from datetime import datetime, timedelta, UTC
from pydantic import BaseModel, Field

import postgresql

WINDOW_SIZE = 128
PREDICTION_WINDOWS = 4
SMOOTHING_ALPHA = 0.25
WIND_ON_THRESHOLD = 0.60
WIND_OFF_THRESHOLD = 0.40
CLASS_LABELS = {
    0: "Control",
    1: "Wind"
}
prediction_state = {}


def normalize_window(values):

    window = numpy.asarray(values, dtype=numpy.float32)
    std = window.std()

    if std == 0:
        return window - window.mean()

    return (window - window.mean()) / std


def smooth_prediction(esp_chip_id, average_probability):

    wind_index = list(model.classes_).index(1)
    wind_probability = float(average_probability[wind_index])

    state = prediction_state.get(
        esp_chip_id,
        {
            "wind_probability": wind_probability,
            "prediction": int(model.classes_[numpy.argmax(average_probability)])
        }
    )

    smoothed_wind_probability = (
        SMOOTHING_ALPHA * wind_probability
        + (1 - SMOOTHING_ALPHA) * state["wind_probability"]
    )

    prediction = state["prediction"]

    if smoothed_wind_probability >= WIND_ON_THRESHOLD:
        prediction = 1
    elif smoothed_wind_probability <= WIND_OFF_THRESHOLD:
        prediction = 0

    prediction_state[esp_chip_id] = {
        "wind_probability": smoothed_wind_probability,
        "prediction": prediction
    }

    confidence = (
        smoothed_wind_probability
        if prediction == 1
        else 1 - smoothed_wind_probability
    )

    return prediction, confidence, smoothed_wind_probability, wind_probability


class SensorPacket(BaseModel):
    esp_chip_id   : str = Field(min_length=12, max_length=12)
    duration    : float = Field(ge=1)
    samples : list[int]


class SessionRequest(BaseModel):
    device_id: int
    label: str = Field(min_length=1, max_length=64)


class StopSessionRequest(BaseModel):
    device_id: int


router = FastAPI()
@router.post('/api/upload')
async def receive_data(request : Request, sensor_packet : SensorPacket, api_key : str = Header()):

    context = request.app.state.context
    config = context.config
    if api_key != config['api']['api_key'] and config['api']['api_key'] != None:
        print(f"[-] alert: unathenticated device {sensor_packet.esp_chip_id}...")
        return {"receieved" : None}
    
    if abs(len(sensor_packet.samples) / sensor_packet.duration - float(config['processing']['samples_per_second'])) > 1:
        warnings.warn("[-] Warning: detecting incoming sensor_packets mistmatch with expected samples per second...", RuntimeWarning)

    received_at = datetime.now(UTC)
    samples     = numpy.asarray(sensor_packet.samples, dtype=numpy.int32)
    
    await postgresql.store_data(context, sensor_packet.esp_chip_id, samples)

    return {"received" : received_at}

@router.get("/api/download")
async def request_data(request : Request, esp_chip_id : str, limit : int = 5000):

    context = request.app.state.context
    samples = await postgresql.request_data(context, esp_chip_id, limit)

    if not samples:
        return []

    return_ = []
    for sample in samples:
        value, timestamp = sample

        return_.append({"value" : value, "timestamp" : timestamp})

    return return_

@router.get("/api/devices")
async def request_devices(request : Request):

    context = request.app.state.context
    devices = await postgresql.list_devices(context)
    
    output = [
        {
            "id": row[0],
            "device_id": row[0],
            "created_at": row[1].isoformat(),
            "esp_chip_id": row[2],
            "active_session_id": context.active_sessions.get(row[0])
        }
        for row in devices
    ]

    return output

@router.post("/api/session/start")
async def start_recording(request : Request, session_request : SessionRequest):

    context = request.app.state.context
    session_id = await postgresql.start_session(
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
async def stop_recording(request : Request, session_request : StopSessionRequest):

    context = request.app.state.context
    session_id = await postgresql.stop_session(
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

model = joblib.load("rf_model.joblib")
@router.get("/api/predict")
async def predict(request: Request, esp_chip_id: str):
    context = request.app.state.context

    requested_samples = WINDOW_SIZE * PREDICTION_WINDOWS
    samples = await postgresql.request_data(context, esp_chip_id, requested_samples)
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
    values = [sample[0] for sample in samples]
    X = []

    for start in range(0, len(values), WINDOW_SIZE):
        window = values[start:start + WINDOW_SIZE]
        X.append(normalize_window(window))

    X = numpy.asarray(X, dtype=numpy.float32)
    probabilities = numpy.asarray(model.predict_proba(X), dtype=numpy.float32)
    average_probability = probabilities.mean(axis=0)

    prediction, confidence, smoothed_wind_probability, instant_wind_probability = (
        smooth_prediction(esp_chip_id, average_probability)
    )

    return {
        "prediction": prediction,
        "label": CLASS_LABELS.get(prediction, str(prediction)),
        "confidence": confidence,
        "sample_count": len(samples),
        "window_size": WINDOW_SIZE,
        "windows_used": available_windows,
        "class_probabilities": {
            CLASS_LABELS.get(int(label), str(label)): float(probability)
            for label, probability in zip(model.classes_, average_probability)
        },
        "instant_wind_probability": instant_wind_probability,
        "smoothed_wind_probability": smoothed_wind_probability,
        "raw_mean": float(numpy.mean(values)),
        "raw_std": float(numpy.std(values))
    }

@router.get("/dashboard")
async def live_dashboard(request : Request):

    templates = request.app.state.templates
    return templates.TemplateResponse(request=request, name="/live.html")

@router.get("/")
async def redirect_dashboard(request : Request):
    return RedirectResponse(url="/dashboard")

def run_api(app : FastAPI, context : postgresql.Context, templates : Jinja2Templates):

    app.state.context = context
    app.state.templates = templates

    config = context.config

    print(f"[+] initializing uvicorn at {config['server']['host']}, {config['server']['port']}...\n")
    uvicorn.run(app, host=config['server']['host'], port=int(config['server']['port']), log_level="warning")

def main(context):

    command = None
    while command not in ("exit", "q"):

        command = input(">> ").strip().lower()
        match command.split():
            case []:
                print("[-] you didn't type anything...")

            case ["session", "start", device_id, label] if device_id.isdigit():

                asyncio.run(
                    postgresql.start_session(
                        context=context,
                        device_id=int(device_id),
                        label=label
                    )
                )

            case ["session", "start", device_id, _]:
                print("[-] device id must be an integer")

            case ["session", "start", *_]:
                print(
                    "[-] proper format:\n"
                    "    session start <device_id> <label>"
                )

            case ["session", "stop", device_id] if device_id.isdigit():

                asyncio.run(
                    postgresql.stop_session(
                        context=context,
                        device_id=int(device_id)
                    )
                )

            case ["session", "stop", *_]:
                print(
                    "[-] proper format:\n"
                    "    session stop <session_id>"
                )

            case ["session", "list"]:

                sessions = asyncio.run(postgresql.list_sessions(context))

                print(
                    f"{'ID':<5}"
                    f"{'DEVICE':<8}"
                    f"{'LABEL':<15}"
                    f"{'STARTED':<22}"
                    f"{'ENDED'}"
                )

                print("-" * 80)

                for session_id, started_at, ended_at, label, device_id in sessions:

                    ended = (
                        ended_at.strftime("%Y-%m-%d %H:%M:%S")
                        if ended_at is not None
                        else "ACTIVE"
                    )

                    print(
                        f"{session_id:<5}"
                        f"{device_id:<8}"
                        f"{label:<15}"
                        f"{started_at.strftime('%Y-%m-%d %H:%M:%S'):<22}"
                        f"{ended}"
                    )

            case ["session"]:
                print(
                    "Available commands:\n"
                    "    session start <device_id> <label>\n"
                    "    session stop <session_id>\n"
                    "    session list"
                )

            case ["device", "list"]:

                devices = asyncio.run(postgresql.list_devices(context))

                print(
                    f"{'ID':<5}"
                    f"{'CHIP ID':<20}"
                    f"{'REGISTERED'}"
                )

                print("-" * 60)

                for device_id, registered_at, chip_id in devices:
                    print(
                        f"{device_id:<5}"
                        f"{chip_id:<20}"
                        f"{registered_at.strftime('%Y-%m-%d %H:%M:%S')}"
                    )

            case ["device"]:
                print(
                    "Available commands:\n"
                    "    device list"
                )

            case ["plot", session_id, limit] if limit.isdigit() and session_id.isdigit():
                rows = asyncio.run(postgresql.request_session_data(
                    context=context,
                    session_id=int(session_id),
                    limit=int(limit)
                ))

                if not rows:
                    print(f"[-] session {session_id} does not exist")

                timestamps = [row[1] for row in rows]
                values = [row[0] for row in rows]

                plt.figure(figsize=(12, 4))
                plt.plot(timestamps, values)

                plt.xlabel("Time")
                plt.ylabel("Signal")
                plt.title("Plant Signal")

                plt.grid(True)
                plt.tight_layout()
                plt.show()

            case ["plot", *_]:
                print(
                    "[-] usage: plot <session_id> [limit]"
                )

            case ["export", session_id, filename] if session_id.isdigit():
                asyncio.run(postgresql.export_session(
                    context=context,
                    session_id=int(session_id),
                    filename=filename
                ))

            case ["export", *_]:
                print(
                    "[-] usage: export <session_id> [filename.csv]"
                )

            case ["exit"] | ["q"]:
                break

            case _:
                print("[-] command not recognized...")
                
    print("\n[-] exiting...\n")    

if __name__ == '__main__':


    config = configparser.ConfigParser()
    config.read('settings.conf')

    templates = Jinja2Templates(directory="./backend/templates")
    context = postgresql.Context(config)

    router.mount(
        "/static",
        StaticFiles(directory="./backend/static"),
        name="static"
    )

    asyncio.run(postgresql.intialize_database(context))

    api_thread = threading.Thread(target=run_api, args=(router, context, templates,), daemon=True)
    api_thread.start()

    main(context)
    print("[-] successfully closed database connetion...")
        
