import socket
from argparse import ArgumentParser
import json
import threading

UDP_PORT = 54321
BROADCAST_IP = "255.255.255.255"


def get_host():
    return socket.gethostname()


def tcp_listen_task(host: str, tcp_port: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, tcp_port))

    print("TCP Listening on", host, tcp_port, flush=True)
    sock.listen()
    while True:
        conn, addr = sock.accept()
        print("Accepted connection from", addr, flush=True)
        conn.close()


def peer_task(peer_host: str, peer_tcp_port: int):
    # connect to peer
    peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    peer_socket.connect((peer_host, peer_tcp_port))
    print(f"Connected to {peer_host}:{peer_tcp_port}", flush=True)
    peer_socket.close()


def peer_ack_task(host: str, tcp_port: int):
    print("Listening for peer acks", flush=True)
    listen_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listen_udp_socket.bind(("0.0.0.0", UDP_PORT))
    print("UDP Listening on", host, UDP_PORT, flush=True)

    while True:
        data, addr = listen_udp_socket.recvfrom(1024)
        # udp is messages
        # so this should be a full json message
        data = json.loads(data.decode())
        print("Received", data, flush=True)
        if data["host"] == host and data["port"] == tcp_port:
            # this is our message
            continue
        # otherwise this is not our message
        if data["type"] == "request":
            # this is a peer request, so we need to respond with an ack
            temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            temp_socket.sendto(
                json.dumps({"type": "ack", "host": host, "port": tcp_port}).encode(),
                (data["host"], 54321),
            )
        else:
            assert data["type"] == "ack"
            # this is an ack, so now we need to create a tcp connection
            threading.Thread(
                target=peer_task, args=(data["host"], data["port"])
            ).start()


def main(host: str, tcp_port: int):
    threading.Thread(target=peer_ack_task, args=(host, tcp_port)).start()
    threading.Thread(target=tcp_listen_task, args=(host, tcp_port)).start()

    # broadcast to udp port
    print("Broadcasting to", BROADCAST_IP, UDP_PORT, flush=True)
    broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    broadcast_socket.sendto(
        json.dumps({"type": "request", "host": host, "port": tcp_port}).encode(),
        (BROADCAST_IP, UDP_PORT),
    )


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--tcp-port", type=str)
    args = parser.parse_args()
    main(get_host(), int(args.tcp_port))
