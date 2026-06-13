import psycopg2



def initialize_database(DATABASE_PARAMETERS):
    
    conn = psycopg2.connect(**DATABASE_PARAMETERS)
    cursor = conn.cursor()
     

def store_sensor_data(cursor):

    # check if it can cleanly put it into the database
    

    pass 
