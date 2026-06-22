import torch
import torch.nn as nn
import torch.nn.functional as F

import configparser, asyncio, uvicorn, psycopg, warnings, numpy, threading

from fastapi import FastAPI, Header, HTTPException, Request
from datetime import datetime, timedelta, UTC
from pydantic import BaseModel, Field


config = configparser.ConfigParser()
config.read('settings.conf')

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


async def intialize_database():
    global config

    async with await psycopg.AsyncConnection.connect(**config['postgresql']) as aconn:
        async with aconn.cursor() as acursor:
            
            initialization = """
            
            CREATE TABLE IF NOT EXISTS Device (
                device_id SERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

                esp_chip_id CHAR(12) NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS Session (
                session_id SERIAL PRIMARY KEY,

                started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMPTZ,

                data_label TEXT NOT NULL,

                device_id INT NOT NULL,
                FOREIGN KEY (device_id)
                    REFERENCES Device(device_id)
            );

            CREATE TABLE IF NOT EXISTS Sample (
                sample_id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

                voltage INTEGER NOT NULL,

                session_id INT NOT NULL,
                FOREIGN KEY (session_id)
                    REFERENCES Session(session_id)
            );
            
            """

            await acursor.execute(initialization)

async def register_device_id(esp_chip_id : str, acursor : psycopg.Cursor):

    await acursor.execute("SELECT * FROM Device WHERE esp_chip_id = %s;", (esp_chip_id,))
    device_id = await acursor.fetchone()

    if device_id:
        return device_id[0]

    await acursor.execute("INSERT INTO Device (esp_chip_id) VALUES (%s) RETURNING device_id;", (esp_chip_id,))
    return (await acursor.fetchone())[0]


class Context:
    def __init__(self):
        self.active_sessions = {}
        self.lock = asyncio.Lock()

async def store_data(context : Context, esp_chip_id : str, samples : numpy.ndarray):
    global config

    async with context.lock:
        session_id = context.active_sessions.get(esp_chip_id)

    if not session_id:
        print(f"[-] alert: device {esp_chip_id} does not have an active session...")
        return

    async with await psycopg.AsyncConnection.connect(**config['postgresql']) as aconn:
        async with aconn.cursor() as acursor:
            
            device_id = await register_device_id(esp_chip_id, acursor)

            parameters = [(sample, session_id,) for sample in samples]
            await acursor.execute("INSERT INTO Sample (voltage, session_id) VALUES (%s, %s):", parameters)


async def list_sessions():
    global config

    async with await psycopg.AsyncConnection.connect(**config['postgresql']) as aconn:
        async with aconn.cursor() as acursor:
            
            await acursor.execute("SELECT * FROM Session;")
            return (await acursor.fetchall())

async def list_devices():
    global config

    async with await psycopg.AsyncConnection.connect(**config['postgresql']) as aconn:
        async with aconn.cursor() as acursor:
            
            await acursor.execute("SELECT * FROM Device;")
            return (await acursor.fetchall())


async def process_data(raw_samples : list):
    samples = numpy.asarray(raw_samples, dtype=numpy.int32)


    return samples

router = FastAPI()
@router.post('/api/upload')
async def receive_data(request : Request, sensor_packet : SensorPacket, api_key : str = Header()):
    global config

    if api_key != config['api']['api_key'] and config['api']['api_key'] != None:
        return {"receieved" : None}
    
    if abs(len(sensor_packet.samples) / sensor_packet.duration - float(config['processing']['samples_per_second'])) > 1:
        warnings.warn("[-] Warning: detecting incoming sensor_packets mistmatch with expected samples per second...", RuntimeWarning)

    received_at = datetime.now(UTC)
    samples     = await process_data(sensor_packet.samples)
    
    await store_data(request.app.state.context, sensor_packet.esp_chip_id, samples)

    return {"received" : received_at}


def run_api(app : FastAPI, context : Context):
    global config

    app.state.context = context

    print(f"[+] initializing uvicorn at {config['server']['host']}, {config['server']['port']}...\n")
    uvicorn.run(app, host=config['server']['host'], port=int(config['server']['port']))

def main():
    global config, router

    context = Context()
    asyncio.run(intialize_database())

    api_thread = threading.Thread(target=run_api, args=(router, context,), daemon=True)
    api_thread.start()

    command = None
    while not command in ('exit', 'q'):
        
        match input(">> ").strip().lower().split():
            case []:
                print("[-] you didn't type anything...")

            case ["session", "start", id]:

                pass

            case ["session", "list"]:
                
                for session in asyncio.run(list_sessions()):
                    print(session)

            case ["session", *wrong_args]:
                print("[-] inappropriate arguments, just say session list :/")
            
            case ["device", "list"]:
                
                for session in asyncio.run(list_devices()):
                    print(session)

            case ["device", *wrong_args]:
                print("[-] inappropriate arguments, just say device list :/")

            case _:
                print("[-] command not recognized...")


    print("\n[-] exiting...\n")    

if __name__ == '__main__':
    main()
    