import psycopg2, functools, os

from datetime import date, UTC, timedelta
from api import routes

class State:
    database = None

def if_online(func):

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if State.database == None: 
            raise PermissionError("System is offline!")
        return func(*args, **kwargs)
    return wrapper


def initialize_database(DATABASE_PARAMETERS):
    
    State.database = psycopg2.connect(**DATABASE_PARAMETERS)
    with State.database.cursor() as cursor:

        initialization = """

            CREATE TABLE IF NOT EXISTS Device (
                device_id SERIAL PRIMARY KEY,
                esp_chip_id CHAR(12) UNIQUE NOT NULL, 
                plant_name TEXT NOT NULL,
                start TIMESTAMPTZ NOT NULL
            );

            CREATE TABLE IF NOT EXISTS Sample (
                id SERIAL PRIMARY KEY,

                adc INT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                device_id INT NOT NULL, 
                FOREIGN KEY (device_id) REFERENCES Device(device_id)  
            );

            CREATE TABLE IF NOT EXISTS Warning (
                warning_id SERIAL PRIMARY KEY, 
                warning_code INT NOT NULL,
                warning_details TEXT,

                device_id INT NOT NULL,
                FOREIGN KEY (device_id) REFERENCES Device(device_id) 
            );
            
        """

        cursor.execute(initialization)
        cursor.connection.commit()


    return State.database


@if_online
def generate_device_table(sensor_data : routes.SensorData, cursor = None):

    temporary = False
    if cursor is None:
        temporary = True  
        cursor = State.database.cursor()

    cursor.execute("SELECT device_id FROM Device WHERE esp_chip_id=%s LIMIT 1;", (sensor_data.esp_chip_id,))
    fetched = cursor.fetchone()

    if fetched == None:
        cursor.execute("INSERT INTO Device (esp_chip_id, plant_name, start) VALUES (%s, %s, %s);",
                    (sensor_data.esp_chip_id, "unassigned", sensor_data.received_at)) 

        cursor.connection.commit()   
        cursor.execute("SELECT device_id FROM Device WHERE esp_chip_id=%s LIMIT 1;", (sensor_data.esp_chip_id,))

        fetched = cursor.fetchone()

    if temporary:
        cursor.close()

    return fetched[0]       

@if_online
def store_sensor_data(sensor_data : routes.SensorData):

    with State.database.cursor() as cursor:

        device_id = generate_device_table(sensor_data, cursor)

        command = "INSERT INTO Sample (device_id, adc, timestamp) VALUES (%s, %s, %s);" 
        parameters = []
        for i, value in enumerate(sensor_data.raw_adc):
            timestamp = sensor_data.received_at + timedelta(i / (len(sensor_data.raw_adc) - 1))
            parameters.append((device_id, value, timestamp,))

        cursor.executemany(command, parameters) 
        cursor.connection.commit()
 
