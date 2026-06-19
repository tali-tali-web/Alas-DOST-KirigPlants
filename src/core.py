import sys, os, uvicorn, threading, configparser, asyncio

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
postgresql.Database.parameters = config["postgresql"]
funnel.alpha = 2 / (int(config['processing']["window_length"]) + 1)
funnel.sps = int(config['processing']['samples_per_second'])

try:
    asyncio.run(postgresql.initialize_database())
    print("[+] Succesfully initialized postgresql!")

    uvicorn.run("api.routes:router", host=server_host, port=server_port)
    

except Exception as e:
    print(e)

