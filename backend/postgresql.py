
import psycopg, asyncio, configparser, numpy

class Context:
    def __init__(self, config : configparser.ConfigParser):
        self.active_sessions = {}
        self.config = config

        self.lock = asyncio.Lock()

async def intialize_database(context : Context):
    
    config = context.config
    async with await psycopg.AsyncConnection.connect(**config['postgresql']) as aconn:
        async with aconn.cursor() as acursor:
            
            initialization = """
            
            CREATE TABLE IF NOT EXISTS Device (
                device_id SERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

                esp_chip_id CHAR(12) NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS Session (
                session_id SERIAL PRIMARY KEY,
                started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

                ended_at TIMESTAMPTZ,
                label TEXT,

                device_id INT NOT NULL,
                FOREIGN KEY (device_id)
                    REFERENCES Device(device_id)
            );

            CREATE TABLE IF NOT EXISTS Sample (
                sample_id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

                voltage INTEGER NOT NULL,

                session_id INT NOT NULL,
                FOREIGN KEY (session_id)
                    REFERENCES Session(session_id)
            );
            
            """

            await acursor.execute(initialization)

async def register_device_id(esp_chip_id : str, acursor : psycopg.Cursor):

    await acursor.execute("SELECT * FROM Device WHERE esp_chip_id = %s;", (esp_chip_id,))
    device_id = await acursor.fetchone()

    if device_id:
        return device_id[0]

    await acursor.execute("INSERT INTO Device (esp_chip_id) VALUES (%s) RETURNING device_id;", (esp_chip_id,))
    return (await acursor.fetchone())[0]

async def store_data(context : Context, esp_chip_id : str, samples : numpy.ndarray):

    config = context.config
    async with await psycopg.AsyncConnection.connect(**config['postgresql']) as aconn:
        async with aconn.cursor() as acursor:
            
            device_id = await register_device_id(esp_chip_id, acursor)

            async with context.lock:
                session_id = context.active_sessions.get(device_id)

            if not session_id:
                print(f"[-] alert: device {device_id}[{esp_chip_id}]: does not have an active session...")
                return

            parameters = [(sample, session_id,) for sample in samples]
            await acursor.executemany("INSERT INTO Sample (voltage, session_id) VALUES (%s, %s);", parameters)

async def start_session(context : Context, device_id : int, label : str):

    config = context.config
    async with context.lock:
        session_id = context.active_sessions.get(device_id)

    if session_id:
        print(f"[-] alert: device {device_id}: already has an active session...")
        return

    async with await psycopg.AsyncConnection.connect(**config['postgresql']) as aconn:
        async with aconn.cursor() as acursor:

            await acursor.execute("INSERT INTO Session (label, device_id) VALUES (%s, %s) RETURNING session_id;", (label, device_id))

            async with context.lock:
                context.active_sessions[device_id] = int((await acursor.fetchone())[0])
                session_id = context.active_sessions[device_id]

    print(
        f"[+] assigned device {device_id} "
        f"to session {session_id} "
        f"with label '{label}'"
    )


async def stop_session(context : Context, device_id : int):

    config = context.config
    async with context.lock:
        session_id = context.active_sessions.get(device_id)

    if not session_id:
        print(f"[-] alert: device {device_id}: does not have an active session...")
        return
        
    async with await psycopg.AsyncConnection.connect(**config['postgresql']) as aconn:
        async with aconn.cursor() as acursor:
            
            await acursor.execute("UPDATE Session SET ended_at=CURRENT_TIMESTAMP WHERE session_id=%s;", (session_id,))

            async with context.lock:
                context.active_sessions[device_id] = None
    
    print(f"[+] stopped session  of device {device_id}")

async def list_sessions(context : Context):

    config = context.config
    async with await psycopg.AsyncConnection.connect(**config['postgresql']) as aconn:
        async with aconn.cursor() as acursor:
            
            await acursor.execute("SELECT * FROM Session;")
            return (await acursor.fetchall())

async def list_devices(context : Context):
    
    config = context.config
    async with await psycopg.AsyncConnection.connect(**config['postgresql']) as aconn:
        async with aconn.cursor() as acursor:
            
            await acursor.execute("SELECT * FROM Device;")
            return (await acursor.fetchall())

