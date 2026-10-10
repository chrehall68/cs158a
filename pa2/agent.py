import socket
from argparse import ArgumentParser
import base64
from datetime import datetime
import json
from pathlib import Path
import struct
import threading
import time


class PeerTable:
    def __init__(self):
        # files are uniquely identified by name
        # peer -> set of file names that it has
        self.peer_to_files: dict[str, set[str]] = {}
        self.peer_to_socket: dict[str, socket.socket] = {}
        # file -> set of peers that have it
        self.file_to_peers: dict[str, set[str]] = {}

    def __remove_peer_files(self, peer: str):
        if peer not in self.peer_to_files:
            return

        for file in self.peer_to_files[peer]:
            self.file_to_peers[file].remove(peer)
            if len(self.file_to_peers[file]) == 0:
                del self.file_to_peers[file]
        del self.peer_to_files[peer]

    def remove_peer(self, peer: str):
        if peer not in self.peer_to_socket:
            return
        self.__remove_peer_files(peer)
        del self.peer_to_socket[peer]

    def register_peer(self, peer: str, socket: socket.socket):
        self.peer_to_socket[peer] = socket
        self.peer_to_files[peer] = set()

    def add_peer_files(self, peer: str, files: set[str]):
        # clean up old files
        self.__remove_peer_files(peer)
        # then just insert the new ones
        self.peer_to_files[peer] = files
        for file in files:
            self.file_to_peers.setdefault(file, set()).add(peer)

    def get_peers_for_file(self, file: str):
        return [
            (peer, self.peer_to_socket[peer])
            for peer in self.file_to_peers.get(file, set())
        ]

    def get_all_peers(self):
        return [(peer, self.peer_to_socket[peer]) for peer in self.peer_to_socket]


UDP_PORT = 54321
BROADCAST_IP = "255.255.255.255"
SHARED_DIR = "shared"
DOWNLOADS_DIR = "downloads"
LOG_FILE = "log.txt"
FILE_LIST_INTERVAL = 10


def log(message: str):
    path = Path(LOG_FILE)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{timestamp} {message}\n")


def send_message(conn: socket.socket, message: dict):
    # Prefix each JSON message with its byte length.
    payload = json.dumps(message).encode("utf-8")
    conn.sendall(struct.pack("!I", len(payload)) + payload)
    log(f"SENT to {conn.getpeername()}, message={message}")


def recv_exact(conn: socket.socket, size: int) -> bytes:
    # TCP may return only part of a message at a time.
    chunks = bytearray()
    while len(chunks) < size:
        chunk = conn.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("Peer disconnected during a message")
        chunks.extend(chunk)
    return bytes(chunks)


def recv_message(conn: socket.socket) -> dict:
    # The 4-byte prefix gives the number of JSON bytes that follow.
    size = struct.unpack("!I", recv_exact(conn, 4))[0]

    # Decode the complete message body after reading its declared length.
    message = json.loads(recv_exact(conn, size).decode("utf-8"))
    log(f"RECEIVED from {conn.getpeername()}, message={message}")
    return message


def _valid_filename(filename: str) -> bool:
    if not filename:
        return False
    # Only allow a filename, not a path supplied by a peer.
    return Path(filename).name == filename and filename not in {
        ".",
        "..",
    }  # prevent peer from accessing any file on system, only shared


def handle_data_request(conn: socket.socket, message: dict):
    # Read the requested filename from the peer's message.
    filename = message.get("filename")
    if not isinstance(filename, str) or not _valid_filename(filename):
        send_message(
            conn,
            {
                "type": "file_error",
                "filename": filename,
                "error": "Invalid filename",
            },
        )
        return

    # Look up the requested file only inside the shared directory.
    file_path = Path(SHARED_DIR) / filename
    if not file_path.is_file():
        # Report missing files without leaving the requester waiting.
        send_message(
            conn,
            {
                "type": "file_error",
                "filename": filename,
                "error": "File is no longer available",
            },
        )
        return

    # Send file data as base64
    send_message(
        conn,
        {
            "type": "file_data",
            "filename": filename,
            "data": base64.b64encode(file_path.read_bytes()).decode(
                "ascii"
            ),  # turn bas64 bytes into string for json serialization
        },
    )


# scan shared directory and return a list of file names
def get_shared_files() -> list[str]:
    shared = Path(SHARED_DIR)
    if not shared.is_dir():
        return []

    try:
        return sorted(p.name for p in shared.iterdir() if p.is_file())
    except OSError as error:
        # report it rather than letting the send fail without a trace
        print(f"Could not read {SHARED_DIR}: {error}")
        return []


# send message to peer which files we have
def send_file_list(conn: socket.socket):
    # use send_message to write to log
    send_message(conn, {"type": "file_list", "files": get_shared_files()})


def handle_file_list(peer_table: PeerTable, peer: str, message: dict):
    files = message.get("files")

    # will probably never happen but just in case
    if not isinstance(files, list):
        files = []

    # update file table with new peer files
    peer_table.add_peer_files(
        peer,
        {file for file in files if _valid_filename(file)},
    )


def request_file_download(conn: socket.socket, filename: str):
    if not _valid_filename(filename):
        raise ValueError("filename must be a single filename, not a path")

    shared_path = Path(SHARED_DIR) / filename
    # Keep the existing copy because files are identified by name only.
    if shared_path.exists():
        raise FileExistsError(f"Already have {filename} in {SHARED_DIR}")

    # Ask the selected peer to send this filename.
    send_message(conn, {"type": "data_request", "filename": filename})


def handle_file_response(message: dict) -> bool:
    # A peer error means there is no file content to save.
    if message.get("type") == "file_error":
        print(message.get("error", "Peer could not serve the file"))
        return False
    if message.get("type") != "file_data":
        raise ValueError("Unexpected message while handling a file response")

    # Validate the peer-provided name before creating local paths.
    filename = message.get("filename")
    if not isinstance(filename, str) or not _valid_filename(filename):
        raise ValueError("Invalid filename in file response")

    shared_path = Path(SHARED_DIR) / filename
    if shared_path.exists():
        return False

    # Decode the complete payload before writing either copy.
    content = base64.b64decode(message["data"], validate=True)
    # Create both destinations when needed.
    downloads_path = Path(DOWNLOADS_DIR)
    downloads_path.mkdir(parents=True, exist_ok=True)
    shared_path.parent.mkdir(parents=True, exist_ok=True)
    download_path = downloads_path / filename
    # Add the file to shared only after the download is complete.
    download_path.write_bytes(content)
    if not shared_path.exists():
        shared_path.write_bytes(content)
        return True
    return False


def prompt_for_download(peer_table: PeerTable):
    while True:
        # Refresh choices so newly advertised files are visible.
        available_files = peer_table.file_to_peers
        if available_files:
            print("Available files:", ", ".join(available_files))
        else:
            print("No files are currently available.")

        try:
            # Read a choice after showing the latest known filenames.
            filename = input("Enter a filename to download, or q to quit: ").strip()
        except EOFError:
            return
        if filename.lower() in {"q", "quit"}:
            return
        if not filename:
            continue

        # Check that at least one peer advertises the chosen name.
        peers = peer_table.get_peers_for_file(filename)
        if not peers:
            print(f"No peer advertises {filename}.")
            continue

        # Choose a connected peer from the advertisers.
        try:
            request_file_download(peers[0][1], filename)
        except (OSError, ValueError) as error:
            print(f"Could not request {filename}: {error}")
        else:
            print(f"Requested {filename}.")


def handle_tcp_connection(
    peer_socket: socket.socket,
    peer_host: str,
    peer_tcp_port: int,
    peer_table: PeerTable,
):
    # Same key is used for the peer table and the file table.
    peer = f"{peer_host}:{peer_tcp_port}"
    with peer_socket:
        # Register the peer now that the TCP connection exists
        peer_table.register_peer(peer, peer_socket)
        log(f"Peer added: {(peer_host, peer_tcp_port)}")

        # Send our file list right away instead of waiting for the next 10 second round
        try:
            send_file_list(peer_socket)
        except OSError:
            # If the peer is already gone, the receive loop below removes it
            pass

        while True:
            # TCP is stream, so get message based on length prefix using recv_message
            try:
                message = recv_message(peer_socket)
            except ConnectionError:
                # Remove the peer and drop the files it advertised
                peer_table.remove_peer(peer)
                log(f"Peer removed: {(peer_host, peer_tcp_port)}")
                break

            if message.get("type") == "data_request":
                # Peer has requested file, so file if we have it or error response if not
                handle_data_request(peer_socket, message)
            elif message.get("type") in {"file_data", "file_error"}:
                # Peer has responded to file request, if data was sent then save to downloads, then shared
                if handle_file_response(message):
                    print(f"Downloaded {message.get('filename')}")
            elif message.get("type") == "file_list":
                # Peer has advertised its files, so update what it has in the file table
                handle_file_list(peer_table, peer, message)
            else:
                # Unsupported message type in format
                print(f"Unexpected message from {peer_host}:{peer_tcp_port}: {message}")


def tcp_accept_task(
    host: str,
    tcp_port: int,
    peer_table: PeerTable,
):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, tcp_port))

    log(f"TCP Listening on {host} {tcp_port}")
    sock.listen()
    while True:
        conn, addr = sock.accept()
        log(f"Accepted connection from {addr}")
        # Spawn a worker thread to serve this peer, then loop back to accept() the next one
        client_thread = threading.Thread(
            target=handle_tcp_connection,
            args=(conn, addr[0], addr[1], peer_table),
            daemon=True,
        )
        client_thread.start()


def file_list_task(peer_table: PeerTable):
    while True:
        time.sleep(FILE_LIST_INTERVAL)
        # Copy the connections so a peer joining or leaving does not break the loop
        for peer, conn in peer_table.get_all_peers():
            try:
                send_file_list(conn)
            except OSError:
                # This peer's receive loop will detect the disconnect and remove it
                continue


def connect_to_peer_task(
    peer_host: str,
    peer_tcp_port: int,
    peer_table: PeerTable,
):
    # connect to peer
    peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    peer_socket.connect((peer_host, peer_tcp_port))
    log(f"Connected to {peer_host}:{peer_tcp_port}")

    # Continue handling TCP connection in this thread
    handle_tcp_connection(peer_socket, peer_host, peer_tcp_port, peer_table)


def peer_ack_task(
    host: str,
    tcp_port: int,
    peer_table: PeerTable,
):
    listen_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listen_udp_socket.bind(("0.0.0.0", UDP_PORT))
    ack_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    log(f"UDP Listening on {host} {UDP_PORT}")

    while True:
        data, addr = listen_udp_socket.recvfrom(1024)
        # udp is messages
        # so this should be a full json message
        data = json.loads(data.decode())
        log(f"RECEIVED from {addr}, message={data}")
        if data["host"] == host and data["port"] == tcp_port:
            # this is our message
            continue
        # otherwise this is not our message
        if data["type"] == "request":
            # this is a peer request, so we need to respond with an ack
            ack_message = {"type": "ack", "host": host, "port": tcp_port}
            ack_socket.sendto(
                json.dumps(ack_message).encode(),
                (data["host"], UDP_PORT),
            )
            log(f"SENT to {(data['host'], UDP_PORT)}, message={ack_message}")
        else:
            assert data["type"] == "ack"
            # this is an ack, so now we need to create a tcp connection
            threading.Thread(
                target=connect_to_peer_task,
                args=(data["host"], data["port"], peer_table),
            ).start()


def main(host: str, tcp_port: int):
    peer_table = PeerTable()
    # Keep network listeners in the background while input runs on the main thread.
    threading.Thread(
        target=peer_ack_task,
        args=(host, tcp_port, peer_table),
        daemon=True,
    ).start()
    threading.Thread(
        target=tcp_accept_task,
        args=(host, tcp_port, peer_table),
        daemon=True,
    ).start()

    # Advertise our file list to every connected peer every 10 seconds.
    threading.Thread(target=file_list_task, args=(peer_table,), daemon=True).start()

    # broadcast to udp port
    broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    request_message = {"type": "request", "host": host, "port": tcp_port}
    broadcast_socket.sendto(
        json.dumps(request_message).encode(),
        (BROADCAST_IP, UDP_PORT),
    )
    log(f"SENT to {(BROADCAST_IP, UDP_PORT)}, message={request_message}")
    # Keep the process interactive until the user quits.
    prompt_for_download(peer_table)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--tcp-port", type=str)
    args = parser.parse_args()
    main(socket.gethostname(), int(args.tcp_port))
