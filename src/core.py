import sys, os, uvicorn, threading, configparser

from api import routes, postgresql
from processing import funnel 



if __name__ == "__main__":

    conf_file = 'settings.conf'

    if not os.path.exists(conf_file):
        raise FileNotFoundError(f"Could not find configuration file at: {conf_file}")

    config = configparser.ConfigParser()
    config.read(conf_file)

    routes.API_KEY = config["api"]["api_key"]
    funnel.window_length = config['processing']["window_length"]
    DATABASE_PARAMETERS = config["postgresql"]


    database = None 
    
    try:

        database = postgresql.initialize_database(DATABASE_PARAMETERS)

        print("[+] Succesfully connected to KirigPlants database!")

        synchronous_worker = threading.Thread(target=funnel.handle_queue, daemon=True)
        synchronous_worker.start()

        print("[+] Succesfully started synchronous funnel worker...")

        uvicorn.run("api.routes:router", host="0.0.0.0", port=8000)
        
    except Exception as e:
        print(e)

    finally:
        if database is not None:
            database.close()

        print("[-] Safely closed the connection...") 
        sys.exit(0)       

