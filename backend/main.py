import configparser, asyncio, uvicorn, warnings, numpy, threading
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


class SensorPacket(BaseModel):
    esp_chip_id   : str = Field(min_length=12, max_length=12)
    duration    : float = Field(ge=1)
    samples : list[int]


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

    devices = await postgresql.list_devices(request.app.state.context)
    
    output = [
        {
            "id": row[0],
            "created_at": row[1].isoformat(),
            "esp_chip_id": row[2]
        }
        for row in devices
    ]

    return output

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
                    print(f"[-] session {sessiond_id} does not exist")

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
        