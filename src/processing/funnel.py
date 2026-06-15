
from api import postgresql, routes
from queue import Queue

window_length = -1
sensor_data_queue = Queue()

def clean_sensor_data(sensor_data : routes.SensorData):
    return sensor_data

def add_queue(sensor_data : routes.SensorData):
    sensor_data_queue.put(sensor_data)

def handle_queue():
    while True:
        sensor_data = sensor_data_queue.get()
        if not isinstance(sensor_data, routes.SensorData):
            raise TypeError(f'Expected SensorData type but got {0}'.format(type(sensor_data)))

        cleaned_sensor_data = clean_sensor_data(sensor_data)
        postgresql.store_sensor_data(cleaned_sensor_data)

