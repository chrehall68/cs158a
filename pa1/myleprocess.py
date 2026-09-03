import socket
import time
import json
from argparse import ArgumentParser
from pathlib import Path
from queue import Queue
from uuid import UUID, uuid4
from threading import Thread
from dataclasses import dataclass

# the actual used size should be less since
# json encoding one of the message objects can't be too big
MAX_BUF_SIZE = 2048


@dataclass
class Message:
    # sender's uuid
    uuid: UUID
    # 0 if still in process of leader election, 1 if elected
    flag: int

    def encode(self):
        return json.dumps({"uuid": str(self.uuid), "flag": self.flag}).encode()

    @staticmethod
    def decode(data):
        items = json.loads(data.decode())
        return Message(uuid=UUID(items["uuid"]), flag=items["flag"])


to_process = Queue()


# https://en.wikipedia.org/wiki/Leader_election#Asynchronous_ring%5B3%5D
def client_task(id, destination_ip, destination_port):
    print("connecting to", destination_ip, destination_port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    to_wait_seconds = 1
    while True:
        try:
            sock.connect((destination_ip, destination_port))
            break
        except ConnectionRefusedError:
            print(
                f"Failed to connect to {destination_ip}:{destination_port}, retrying in {to_wait_seconds} seconds"
            )
            to_wait_seconds *= 2
            time.sleep(to_wait_seconds)
    # clients are actually the ones that send, while servers
    # are the ones that receive
    print(f"Client {id} connected to {destination_ip}:{destination_port}")

    # initialization -> send id
    sock.send(Message(id, 0).encode())
    while True:
        message = to_process.get()
        if message.flag == 2:
            break
        sock.send(message.encode())

    sock.close()


def server_task(id, server_ip, server_port):
    print("listening on", server_ip, server_port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((server_ip, server_port))
    sock.listen()
    conn, _addr = sock.accept()
    print("Server started")

    received_leader_message = False
    leader = None
    while not received_leader_message:
        # wait for message from client
        data = conn.recv(MAX_BUF_SIZE)
        message = Message.decode(data)
        print(f"Received {message}")

        if message.flag == 1:
            received_leader_message = True
            leader = message.uuid

        if message.uuid > id:
            # forward along
            to_process.put(message)
        elif message.uuid == id:
            if message.flag == 0:
                # forward saying that now I am the leader
                # but keep ourselves alive that way we can receive
                # the forwarded message
                to_process.put(Message(id, 1))
        # otherwise, nothing to do
        else:
            pass
    # tell receiver to stop
    to_process.put(Message(id, 2))
    print(f"Leader is {leader}")


def main(config_file: Path):
    my_id = uuid4()
    # config.txt
    with open(config_file, "r") as f:
        lines = f.readlines()
        my_server_ip, my_server_port = lines[0].split(",")
        my_server_port = int(my_server_port)
        destination_server_ip, destination_server_port = lines[1].split(",")
        destination_server_port = int(destination_server_port)
    t1 = Thread(
        target=client_task, args=(my_id, destination_server_ip, destination_server_port)
    )
    t2 = Thread(target=server_task, args=(my_id, my_server_ip, my_server_port))
    t1.start()
    t2.start()
    t1.join()
    t2.join()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("config_file", type=Path)
    args = parser.parse_args()
    main(args.config_file)
