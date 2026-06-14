import psycopg2

from datetime import date, UTC, timedelta
from api import routes

def initialize_database(DATABASE_PARAMETERS):
    
    conn = psycopg2.connect(**DATABASE_PARAMETERS)
    cursor = conn.cursor()
     
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
            device_id INT  NOT NULL, 
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

    return conn, cursor


def check_user_id(cursor, SensorData : routes.SensorData):
    cursor.execute("SELECT * FROM Device WHERE esp_chip_id=%s", (SensorData.ESP_ID,))
    return len(cursor.fetchall()) > 0

def generate_device_table(cursor, SensorData : routes.SensorData, plant_name : str = "unassigned"):

    if check_user_id(cursor, SensorData):
        return False

    command = "INSERT INTO Device (esp_chip_id, plant_name, start) VALUES (%s, %s, %s);"
    cursor.execute(command, (SensorData.ESP_ID, plant_name, SensorData.received_at))    

    return True

def store_sensor_data(cursor, SensorData : routes.SensorData):

    if not check_user_id(cursor, SensorData):
        _ = generate_device_table(cursor, SensorData)
    
    for i, value in enumerate(SensorData.data):
        timestamp = SensorData.received_at + timedelta(i / (len(SensorData.data) - 1))

        command = "INSERT INTO Sample (device_id, adc, timestamp) VALUES (%s, %s, %s)" 
        cursor.execute(command, (SensorData.device_id, value, timestamp,)) 

    return True

