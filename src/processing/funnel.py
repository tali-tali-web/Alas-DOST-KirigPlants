
from api import postgresql, routes
from machine_learning import pipeline

from queue import Queue

import asyncio, socket, math, time

sps = 0
window_length = 0
context = {}
lock = asyncio.Lock()

plotter_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
plotter_socket.setblocking(False)

async def iterate(esp_chip_id : str, data_batch : list):
    global lock, context, window_length 
    
    async with lock:

        if esp_chip_id not in context:
            context[esp_chip_id] = ([], ('127.0.0.1', 9999+len(context)) )

            print(f"[+] created new output at {context[esp_chip_id][-1]}...")
            
        window, output_params = context[esp_chip_id]

        window.extend(data_batch)
        while len(window) > window_length:
            prediction = await pipeline.receive_data(window[:window_length])
            del window[:window_length]
        

  











