
from api import postgresql, routes
from queue import Queue

import asyncio, socket, math, time

sps = 0
alpha = 0
context = {}
lock = asyncio.Lock()

plotter_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
plotter_socket.setblocking(False)

async def iterate(esp_chip_id : str, value : int, stream : bool = False) -> float:
    global plotter_socket, lock, context, alpha
    
    normalized = None
    async with lock:

        if esp_chip_id not in context:
            context[esp_chip_id] = (value, 0, ('127.0.0.1', 9999+len(context)) )

            print(f"[+] created new output at {context[esp_chip_id][-1]}...")

            return value

        previous_ema, previous_variance, output_params = context[esp_chip_id]

        current_ema = value * alpha + previous_ema * (1.0 - alpha)   
        current_variance = alpha * (value - current_ema) * (value - previous_ema) + previous_variance * (1.0 - alpha)

        context[esp_chip_id] = (current_ema, current_variance, output_params)
        
        normalized = (value - current_ema) / max(math.sqrt(max(current_variance, 0.0)), 0.0001)

    if stream:
        packet = f"{normalized}\n".encode('utf-8')    
        await asyncio.get_running_loop().sock_sendto(plotter_socket, packet, output_params)    

    return normalized
  











