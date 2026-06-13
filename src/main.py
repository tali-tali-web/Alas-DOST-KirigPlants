import sys, os

import api.routes, api.postgresql, processing.parse_data


def main():
    pass 

if __name__ == "__main__":


    DATABASE_PARAMETERS = {
                            "database" : "db_name",
                            "host" : "db_host",
                            "user" : "db_user",
                            "password" : "db_pass",
                            "port" : "db_port"
                        }   

    database, cursor = api.postgresql.initialize_database(DATABASE_PARAMETERS)

    main()
