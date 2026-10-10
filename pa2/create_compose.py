from argparse import ArgumentParser
from pathlib import Path
import os

NETWORK_STRING = """
networks:
    pa3:
        driver: bridge
"""


def get_service_string(i):
    return f"""
    machine{i}:
        build: .
        command: python3 agent.py --tcp-port 8900
        volumes:
            - ./shared{i}:/app/shared
            - ./downloads{i}:/app/downloads
            - ./log{i}.txt:/app/log.txt
        tty: true
        init: true
        stdin_open: true
    """


def main(n: int):
    with open("docker-compose.yml", "w") as f:
        f.write("services:\n")
        for i in range(1, n + 1):
            f.write(get_service_string(i))
            open(f"log{i}.txt", "w").close()
            Path(f"shared{i}").mkdir(exist_ok=True)
            Path(f"downloads{i}").mkdir(exist_ok=True)
        f.write(NETWORK_STRING)


parser = ArgumentParser()
parser.add_argument("n", type=int)
if __name__ == "__main__":
    args = parser.parse_args()
    main(args.n)

    os.execvp("docker", ["docker", "compose", "up", "--build"])
