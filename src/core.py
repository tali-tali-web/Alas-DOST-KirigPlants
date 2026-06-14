import sys, os, uvicorn

from api import routes, postgresql
from processing import parser 




if __name__ == "__main__":


    DATABASE_PARAMETERS = {
                            "database" : "kirigplants",
                            "host" : "10.172.50.240",
                            "user" : "postgres",
                            "password" : "your-secure-password",
                            "port" : "5432"
                        }   

    database = None 
    
    try:

        database = postgresql.initialize_database(DATABASE_PARAMETERS)

        print("[+] Succesfully connected to KirigPlants database!")

        uvicorn.run("api.routes:router", host="0.0.0.0", port=8000)
    except Exception as e:
        print(e)

    finally:
        if database is not None:
            database.close()

        print("[-] Safely closed the connection...") 
        sys.exit(0)       

