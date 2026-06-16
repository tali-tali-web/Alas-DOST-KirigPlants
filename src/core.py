import sys, os, uvicorn, threading, configparser

from api import routes, postgresql
from processing import funnel 



conf_file = 'settings.conf'
if __name__ != "__main__":
    sys.exit(0)
elif not os.path.exists(conf_file):
    raise FileNotFoundError(f"Could not find configuration file at: {conf_file}")
    
config = configparser.ConfigParser()
config.read(conf_file)

server_host = config["server"]["host"]
server_port = int(config["server"]["port"])
routes.API_KEY = config["api"]["api_key"]
DATABASE_PARAMETERS = config["postgresql"]
funnel.alpha = 2 / (int(config['processing']["window_length"]) + 1)

database = None 
try:

    database = postgresql.initialize_database(DATABASE_PARAMETERS)

    print("[+] Succesfully connected to KirigPlants database!")

    synchronous_worker = threading.Thread(target=funnel.handle_queue, daemon=True)
    synchronous_worker.start()

    print("[+] Succesfully started synchronous funnel worker...")

    machine_learning_worker = threading.Thread(target=funnel.handle_processing, daemon=True)
    machine_learning_worker.start()

    uvicorn.run("api.routes:router", host=server_host, port=server_port)
    

except Exception as e:
    print(e)

finally:
    if database is not None:
        database.close()

    print("[-] Safely closed the connection...") 
    sys.exit(0)       

