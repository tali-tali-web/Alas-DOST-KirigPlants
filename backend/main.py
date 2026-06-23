import torch
import torch.nn as nn
import torch.nn.functional as F

import configparser, asyncio, uvicorn, warnings, numpy, threading

from fastapi import FastAPI, Header, HTTPException, Request
from datetime import datetime, timedelta, UTC
from pydantic import BaseModel, Field


import postgresql

class StressTestCNN(nn.Module):

    def __init__(self):
        super().__init__()

        self.layers = nn.ModuleList([
            nn.Conv1d(1, 16, 5),
            nn.ReLU(),
            nn.MaxPool1d(2),

            nn.Conv1d(16, 32, 5),
            nn.ReLU(),
            nn.MaxPool1d(2),
        ])

    def forward(self, x):
        for layer in self.layers:
            x = layer(x)

class SensorPacket(BaseModel):
    esp_chip_id   : str = Field(min_length=12, max_length=12)
    duration    : float = Field(ge=1)
    samples : list[int]

router = FastAPI()
@router.post('/api/upload')
async def receive_data(request : Request, sensor_packet : SensorPacket, api_key : str = Header()):
    global config

    if api_key != config['api']['api_key'] and config['api']['api_key'] != None:
        (f"[-] alert: unathenticated device {sensor_packet.esp_chip_id}...")
        return {"receieved" : None}
    
    if abs(len(sensor_packet.samples) / sensor_packet.duration - float(config['processing']['samples_per_second'])) > 1:
        warnings.warn("[-] Warning: detecting incoming sensor_packets mistmatch with expected samples per second...", RuntimeWarning)

    received_at = datetime.now(UTC)
    samples     = numpy.asarray(sensor_packet.samples, dtype=numpy.int32)
    
    await postgresql.store_data(request.app.state.context, sensor_packet.esp_chip_id, samples)

    return {"received" : received_at}


def run_api(app : FastAPI, context : postgresql.Context):
    global config

    app.state.context = context

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

            case ["exit"] | ["q"]:
                break

            case _:
                print("[-] command not recognized...")
                
    print("\n[-] exiting...\n")    

if __name__ == '__main__':

    config = configparser.ConfigParser()
    config.read('settings.conf')

    context = postgresql.Context(config)
    asyncio.run(postgresql.intialize_database(context))

    api_thread = threading.Thread(target=run_api, args=(router, context,), daemon=True)
    api_thread.start()

    main(context)
    print("[-] successfully closed database connetion...")
        