import psycopg, functools, os, asyncio

from datetime import date, UTC, timedelta
from api import routes

class Database:
    parameters : dict = None

async def initialize_database():
    
    async with await psycopg.AsyncConnection.connect(**Database.parameters) as aconn:
        async with aconn.cursor() as acursor:

            initialization = """

                CREATE TABLE IF NOT EXISTS Device (
                    device_id SERIAL PRIMARY KEY,
                    esp_chip_id CHAR(12) UNIQUE NOT NULL, 
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                ); 

                CREATE TABLE IF NOT EXISTS Sample (
                    sample_id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

                    voltage FLOAT NOT NULL,
                    device_id INT NOT NULL, 
                    FOREIGN KEY (device_id) REFERENCES Device(device_id)  
                );

                CREATE TABLE IF NOT EXISTS Prediction (
                    prediction_id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

                    light_level FLOAT NOT NULL,
                    water_stress FLOAT NOT NULL,
                    mechanical_stress FLOAT NOT NULL,

                    device_id INT NOT NULL,
                    FOREIGN KEY (device_id) REFERENCES Device(device_id)
                );
                
            """

            await acursor.execute(initialization)


async def register_device(esp_chip_id : str, acursor : psycopg.Cursor) -> int:
    
    await acursor.execute("SELECT device_id FROM Device WHERE esp_chip_id = %s;", (esp_chip_id,))
    device_id = await acursor.fetchone()
    if device_id == None:
        
        await acursor.execute("INSERT INTO Device (esp_chip_id) VALUES (%s) RETURNING device_id;", (esp_chip_id,))
        device_id = await acursor.fetchone()
    
    return device_id[0]


async def store_data(esp_chip_id : str, data_list : list):

    async with await psycopg.AsyncConnection.connect(**Database.parameters) as aconn:
        async with aconn.cursor() as acursor:
            
            device_id = await register_device(esp_chip_id, acursor)
            parameters = [(datapoint, device_id,) for datapoint in data_list]
            await acursor.executemany("INSERT INTO Sample (voltage, device_id) VALUES (%s, %s);", parameters)
