
import time
import requests
import random
import math

URL = "http://127.0.0.1:8000/api/upload"

HEADERS = {
    "Content-Type": "application/json",
    "api-key": "something-stupid-over-here"
}

SPS = 32
BATCH_SIZE = 128

sample_counter = 0

while True:

    samples = [
        sample_counter
        for i in range(
            sample_counter,
            sample_counter + BATCH_SIZE
        )
    ]

    payload = {
        "esp_chip_id": "012301230123",
        "duration": BATCH_SIZE / SPS,
        "samples": samples
    }

    response = requests.post(
        URL,
        json=payload,
        headers=HEADERS,
        timeout=5
    )

    print(
        response.status_code,
        response.text
    )

    sample_counter += BATCH_SIZE

    time.sleep(BATCH_SIZE / SPS)
