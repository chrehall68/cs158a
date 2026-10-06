TCP: 4-byte length prefix, followed by a UTF-8 JSON message.
TCP bodies: `file_list {type,files}`, `data_request {type,filename}`, `file_data {type,filename,data}` (`data` is base64), `file_error {type,filename,error}`.
UDP: one UTF-8 JSON datagram, either `request` or `ack`, each with `{type,host,port}`.
