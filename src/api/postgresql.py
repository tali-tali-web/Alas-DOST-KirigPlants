import psycopg2



def initialize_database(DATABASE_PARAMETERS):
    
    conn = psycopg2.connect(**DATABASE_PARAMETERS)
    cursor = conn.cursor()
     
    initialization = """


        CREATE TABLE Device IF NOT EXISTS ()
            device_id SERIAL PRIMARY KEY,
            esp_chip_id CHAR(12) UNIQUE NOT NULL, 
            plant_name TEXT NOT NULL,

            start DATE DEFAULT CURRENT_DATE
        );

        CREATE TABLE Sample IF NOT EXISTS (
            id SERIAL PRIMARY KEY,

            value INT,
            timestamp TIMESTAMP,

            device_id INT  NOT NULL, 
            FOREIGN KEY (device_id) REFERENCES Device(device_id)  
        );

        CREATE TABLE Warning IF NOT EXISTS (
            warning_id SERIAL PRIMARY_KEY, 
            warning_code INT NOT NULL,
            warning_details TEXT,
            
            device_id INT NOT NULL,
            FOREIGN KEY (device_id) REFERENCES Device(device_id) 
        );
        
    """

    cursor.execute(initialization)

    return conn, cursor

def store_sensor_data(cursor):

    # check if it can cleanly put it into the database
    """
        INSERT INTO sample (ESP_ID, cleaned_data, timestamp, etc) VALUES (%s, %s, %s, %s); 
    """

    pass 
