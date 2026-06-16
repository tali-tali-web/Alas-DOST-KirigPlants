
from api import postgresql, routes
from queue import Queue

import asyncio




async def assign_new_context(esp_chip_id : str):
    pass



alpha = 0
context = {}
lock = asyncio.Lock()

async def iterate(esp_chip_id : str, timestamp : str, value : int):
    global lock, context, alpha

    normalized = None
    async with lock:

        if esp_chip_id not in context or not context[esp_chip_id][0]:
            context[esp_chip_id] = (True, value, 0)
            return value

        _, previous_ema, previous_variance = context[esp_chip_id]

        current_ema = value * alpha + previous_ema * (1.0 - alpha)   
        current_variance = math.sqrt((1 - alpha) * (previous_variance + alpha * (value - previous_ema) ** 2))
        
        context[esp_chip_id] = (True, current_ema, current_variance)
        
        normalized = (value - current_ema) / max(0.00001, current_variance)
        
    return normalized

    


