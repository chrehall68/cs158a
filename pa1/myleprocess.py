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
    def decode(data: str):
        try:
            items = json.loads(data)
            return Message(uuid=UUID(items["uuid"]), flag=items["flag"])
        except json.JSONDecodeError:
            raise RuntimeError(f"Failed to decode {data}")

    @staticmethod
    def decode_from_buffer(data: str) -> tuple["Message | None", str]:
        # because we know we just have UUIDs and an integer,
        # we know "}" is the end of a message
        # we have to do this since we aren't guaranteed that messages arrive
        # one at a time since tcp is a stream
        # (and it happened to me that sometimes conn.recv() would return multiple messages at once)
        if "}" in data:
            substr = data[: data.find("}") + 1]
            remaining = data[len(substr) :]
            return Message.decode(substr), remaining
        else:
            return None, data


to_process = Queue()


# https://en.wikipedia.org/wiki/Leader_election#Asynchronous_ring%5B3%5D
def client_task(log_writer, id, destination_ip, destination_port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        to_wait_seconds = 1
        while True:
            try:
                sock.connect((destination_ip, destination_port))
                break
            except ConnectionRefusedError:
                print(
                    f"Failed to connect to {destination_ip}:{destination_port}, retrying in {to_wait_seconds} seconds"
                )
                time.sleep(to_wait_seconds)
        # clients are actually the ones that send, while servers
        # are the ones that receive
        print(f"Client {id} connected to {destination_ip}:{destination_port}")

        # initialization -> send id
        sock.sendall(Message(id, 0).encode())
        while True:
            message = to_process.get()
            if message.flag == 2:
                break
            sock.sendall(message.encode())
            log_writer.write(f"Sent {message}\n")


def server_task(log_writer, id, server_ip, server_port):
    print("Listening on", server_ip, server_port)
    TIME_WAIT_SECONDS = 1
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # so technically on linux, we could just not set this, but then
        # according to https://stackoverflow.com/questions/3229860/what-is-the-meaning-of-so-reuseaddr-setsockopt-option-linux
        # we would have to wait a while before we can rebind
        # (and thus wait a while before re-running this program)
        # I've lowered it down to just 1 second that way we can
        # re-run this program more quickly, but there's still the possibility
        # that late packets will arrive from the previous run
        # and maybe cause issues
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, TIME_WAIT_SECONDS)
        sock.bind((server_ip, server_port))
        sock.listen()
        conn, _addr = sock.accept()
        with conn:
            print(f"Server {id} started")
            received_leader_message = False
            knows_leader = False
            leader = None
            buf = ""
            while not received_leader_message:
                # wait for message from client
                data = conn.recv(MAX_BUF_SIZE)
                buf += data.decode()

                message, buf = Message.decode_from_buffer(buf)
                while message is not None:
                    if message.flag == 1:
                        knows_leader = True
                        received_leader_message = True
                        leader = message.uuid

                    if message.uuid > id:
                        # forward along
                        to_process.put(message)
                    elif message.uuid == id:
                        # if 1, we are already the leader and don't need to do anything
                        if message.flag == 0:
                            # forward saying that now I am the leader
                            # but keep ourselves alive that way we can receive
                            # the forwarded message
                            knows_leader = True
                            leader = id
                            to_process.put(Message(id, 1))
                    # otherwise, nothing to do since it's <

                    # log
                    greater_message = "greater"
                    if message.uuid < id:
                        greater_message = "less, so ignored it"
                    elif message.uuid == id:
                        greater_message = "equal"
                    leader_message = "0"
                    if knows_leader:
                        leader_message = leader
                    log_writer.write(
                        f"Received {message}, {greater_message}, leader={leader_message}\n"
                    )

                    # advance
                    message, buf = Message.decode_from_buffer(buf)

            # now that we have a leader,
            # tell receiver to stop by sending a 2
            to_process.put(Message(id, 2))
            print(f"Leader is {leader}")
            assert buf == ""


def main(config_file: Path, log_file: Path):
    my_id = uuid4()
    # the config should just be 2 lines:
    # my_server_ip, my_server_port
    # destination_server_ip, destination_server_port
    with open(config_file, "r") as f:
        lines = f.readlines()
        my_server_ip, my_server_port = lines[0].split(",")
        my_server_port = int(my_server_port)
        destination_server_ip, destination_server_port = lines[1].split(",")
        destination_server_port = int(destination_server_port)

    with open(log_file, "w") as f:
        f.write(f"Log for {my_id}\n")
        t1 = Thread(
            target=client_task,
            args=(f, my_id, destination_server_ip, destination_server_port),
        )
        t2 = Thread(target=server_task, args=(f, my_id, my_server_ip, my_server_port))
        t1.start()
        t2.start()
        t1.join()
        t2.join()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("config_file", type=Path)
    parser.add_argument("log_file", type=Path)
    args = parser.parse_args()
    main(args.config_file, args.log_file)
