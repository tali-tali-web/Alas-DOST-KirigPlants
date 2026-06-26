import configparser
import matplotlib.pyplot as plt

import postgresql
import selectors

def run_cli(context):
    while True:
        command = input(">> ").strip().lower()
        parts = command.split()

        if not parts:
            print("[-] you didn't type anything...")
            continue

        match parts:
            case ["session", "start", device_id, label] if device_id.isdigit():
                session_id = postgresql.start_session(
                    context=context,
                    device_id=int(device_id),
                    label=label
                )
                print(f"[+] started session {session_id}")

            case ["session", "start", *_]:
                print("[-] usage: session start <device_id> <label>")

            case ["session", "stop", device_id] if device_id.isdigit():
                session_id = postgresql.stop_session(
                    context=context,
                    device_id=int(device_id)
                )

                if not session_id:
                    print("[-] no active session found")
                else:
                    print(f"[+] stopped session {session_id}")

            case ["session", "stop", *_]:
                print("[-] usage: session stop <device_id>")

            case ["session", "list"]:
                sessions = postgresql.list_sessions(context)

                print(
                    f"{'ID':<6}"
                    f"{'DEVICE':<10}"
                    f"{'LABEL':<15}"
                    f"{'STARTED':<22}"
                    f"{'ENDED'}"
                )
                print("-" * 80)

                for session_id, started_at, ended_at, label, device_id in sessions:
                    ended = (
                        ended_at.strftime("%Y-%m-%d %H:%M:%S")
                        if ended_at else "ACTIVE"
                    )

                    print(
                        f"{session_id:<6}"
                        f"{device_id:<10}"
                        f"{label:<15}"
                        f"{started_at.strftime('%Y-%m-%d %H:%M:%S'):<22}"
                        f"{ended}"
                    )

            case ["device", "list"]:
                devices = postgresql.list_devices(context)

                print(f"{'ID':<6}{'CHIP ID':<20}{'REGISTERED'}")
                print("-" * 60)

                for device_id, registered_at, chip_id in devices:
                    print(
                        f"{device_id:<6}"
                        f"{chip_id:<20}"
                        f"{registered_at.strftime('%Y-%m-%d %H:%M:%S')}"
                    )

            case ["plot", session_id, limit] if session_id.isdigit() and limit.isdigit():
                rows = postgresql.request_session_data(
                    context=context,
                    session_id=int(session_id),
                    limit=int(limit)
                )

                if not rows:
                    print(f"[-] session {session_id} not found or empty")
                    continue

                timestamps = [r[1] for r in rows]
                values = [r[0] for r in rows]

                plt.figure(figsize=(12, 4))
                plt.plot(timestamps, values)

                plt.xlabel("Time")
                plt.ylabel("Signal")
                plt.title(f"Session {session_id} Signal")
                plt.grid(True)
                plt.tight_layout()
                plt.show()


            case ["plot", *_]:
                print("[-] usage: plot <session_id> <limit>")

            case ["export", session_id, filename] if session_id.isdigit():
                postgresql.export_session(
                    context=context,
                    session_id=int(session_id),
                    filename=filename
                )
                print(f"[+] exported session {session_id} → {filename}")

            case ["export", *_]:
                print("[-] usage: export <session_id> <filename.csv>")


            case ["exit"] | ["q"]:
                break

            case _:
                print("[-] command not recognized")

def main():
    config = configparser.ConfigParser()
    config.read("settings.conf")

    context = postgresql.Context(config)

    print("[+] initializing database...")
    postgresql.initialize_database(context)

    print("[+] CLI ready (type 'exit' to quit)\n")
    run_cli(context)

    print("[-] CLI closed")


if __name__ == "__main__":
    main()