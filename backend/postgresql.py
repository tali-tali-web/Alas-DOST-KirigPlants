import psycopg
import configparser
import numpy as np


class Context:
    def __init__(self, config: configparser.ConfigParser):
        self.active_sessions = {}
        self.config = config

def initialize_database(context: Context):

    with psycopg.connect(**context.config["postgresql"]) as conn:
        with conn.cursor() as cur:
            cur.execute("""
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
                    device_id INT NOT NULL REFERENCES Device(device_id)
                );

                CREATE TABLE IF NOT EXISTS Sample (
                    sample_id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    voltage INTEGER NOT NULL,
                    session_id INT NOT NULL REFERENCES Session(session_id)
                );
            """)


def register_device_id(esp_chip_id: str, cur):

    cur.execute(
        "SELECT device_id FROM Device WHERE esp_chip_id=%s;",
        (esp_chip_id,)
    )
    row = cur.fetchone()

    if row:
        return row[0]

    cur.execute(
        "INSERT INTO Device (esp_chip_id) VALUES (%s) RETURNING device_id;",
        (esp_chip_id,)
    )
    return cur.fetchone()[0]


def store_data(context: Context, esp_chip_id: str, samples: np.ndarray):

    with psycopg.connect(**context.config["postgresql"]) as conn:
        with conn.cursor() as cur:

            device_id = register_device_id(esp_chip_id, cur)

            session_id = context.active_sessions.get(device_id)

            if not session_id:
                return

            cur.executemany(
                "INSERT INTO Sample (voltage, session_id) VALUES (%s, %s);",
                [(int(s), session_id) for s in samples]
            )


def request_data(context: Context, esp_chip_id: str, limit: int):

    with psycopg.connect(**context.config["postgresql"]) as conn:
        with conn.cursor() as cur:

            cur.execute(
                "SELECT device_id FROM Device WHERE esp_chip_id=%s;",
                (esp_chip_id,)
            )
            row = cur.fetchone()

            if not row:
                return []

            device_id = row[0]

            session_id = context.active_sessions.get(device_id)

            if not session_id:
                return []

            cur.execute("""
                SELECT voltage, timestamp
                FROM Sample
                WHERE session_id=%s
                ORDER BY sample_id DESC
                LIMIT %s;
            """, (session_id, limit))

            return cur.fetchall()


def request_session_data(context: Context, session_id: int, limit: int):

    with psycopg.connect(**context.config["postgresql"]) as conn:
        with conn.cursor() as cur:

            cur.execute(
                "SELECT * FROM Session WHERE session_id=%s;",
                (session_id,)
            )
            session = cur.fetchone()

            if not session:
                return []

            if limit > 0:
                cur.execute("""
                    SELECT voltage, sample_id
                    FROM Sample
                    WHERE session_id=%s
                    ORDER BY sample_id ASC
                    LIMIT %s;
                """, (session_id, limit))
            else:
                cur.execute("""
                    SELECT voltage, sample_id
                    FROM Sample
                    WHERE session_id=%s
                    ORDER BY sample_id ASC;
                """, (session_id,))

            return cur.fetchall()


def start_session(context: Context, device_id: int, label: str):

    if context.active_sessions.get(device_id):
        return None

    with psycopg.connect(**context.config["postgresql"]) as conn:
        with conn.cursor() as cur:

            cur.execute(
                "INSERT INTO Session (label, device_id) VALUES (%s, %s) RETURNING session_id;",
                (label, device_id)
            )

            session_id = cur.fetchone()[0]
            context.active_sessions[device_id] = session_id

            return session_id


def stop_session(context: Context, device_id: int):

    session_id = context.active_sessions.get(device_id)

    if not session_id:
        return None

    with psycopg.connect(**context.config["postgresql"]) as conn:
        with conn.cursor() as cur:

            cur.execute(
                "UPDATE Session SET ended_at=CURRENT_TIMESTAMP WHERE session_id=%s;",
                (session_id,)
            )

            context.active_sessions[device_id] = None
            return session_id


def list_sessions(context: Context):

    with psycopg.connect(**context.config["postgresql"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM Session;")
            return cur.fetchall()


def list_devices(context: Context):

    with psycopg.connect(**context.config["postgresql"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM Device;")
            return cur.fetchall()
        
def export_session(context: Context, session_id: int, filename: str):

    with psycopg.connect(**context.config["postgresql"]) as conn:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT voltage, timestamp
                FROM Sample
                WHERE session_id=%s
                ORDER BY sample_id ASC;
            """, (session_id,))

            rows = cur.fetchall()

    with open(filename, "w", encoding="utf-8") as f:
        f.write("value,timestamp\n")

        for value, timestamp in rows:
            f.write(f"{value},{timestamp}\n")