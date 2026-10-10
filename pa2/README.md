TCP: 4-byte length prefix, followed by a UTF-8 JSON message.
TCP bodies: `file_list {type,files}`, `data_request {type,filename}`, `file_data {type,filename,data}` (`data` is base64), `file_error {type,filename,error}`.
UDP: one UTF-8 JSON datagram, either `request` or `ack`, each with `{type,host,port}`.

## Running

Requires Docker with the Compose plugin.

1. From `pa2/`, generate the compose file and start `n` machines:

   ```sh
   python3 create_compose.py n
   ```

   This writes `docker-compose.yml`, creates `shared<i>/`, `downloads<i>/` and `log<i>.txt` for each machine, then runs `docker compose up --build`. Put seed files in `shared<i>/`. Downloaded files will land in `downloads<i>/`.

2. In another terminal (still in `pa2/`), you can attach to a specific machine to execute download commands:

   ```sh
   ./attach.sh <i>
   ```
