This is actually for PA2 (the socket programming / leader election program)

# Running the program

```sh
python3 run.py 3
```

This will run 3 versions of the `myleprocess.py` programs in parallel
with different configs (`config1.txt`, `config2.txt`, `config3.txt`)
that force them to act as a ring.

Each `myleprocess.py` will write to its own log file (ie `log1.txt`, `log2.txt`, `log3.txt`).

# Example:

```
➜  pa1 (main) python3 ./run.py 3                                              ✗ ✭ ✱
Listening on 0.0.0.0 8900
Failed to connect to 0.0.0.0:8901, retrying in 1 seconds
Listening on 0.0.0.0 8901
Failed to connect to 0.0.0.0:8902, retrying in 1 seconds
Listening on 0.0.0.0 8902
Client 0c7bcbb0-b9ea-439e-aa91-f8b7afb45139 connected to 0.0.0.0:8900
Server e2f044bf-8dab-4384-ac13-708494f0ea8d started
cClient e2f044bf-8dab-4384-ac13-708494f0ea8d connected to 0.0.0.0:8901
Server dcd941ad-6bb9-4ed5-86a9-649c2b980f3c started
Client dcd941ad-6bb9-4ed5-86a9-649c2b980f3c connected to 0.0.0.0:8902
Server 0c7bcbb0-b9ea-439e-aa91-f8b7afb45139 started
Leader is e2f044bf-8dab-4384-ac13-708494f0ea8d
Leader is e2f044bf-8dab-4384-ac13-708494f0ea8d
Leader is e2f044bf-8dab-4384-ac13-708494f0ea8d
➜  pa1 (main) cat ./log1.txt                                                  ✗ ✭ ✱
Log for e2f044bf-8dab-4384-ac13-708494f0ea8d
Received Message(uuid=UUID('0c7bcbb0-b9ea-439e-aa91-f8b7afb45139'), flag=0), less, so ignored it, leader=0
Received Message(uuid=UUID('dcd941ad-6bb9-4ed5-86a9-649c2b980f3c'), flag=0), less, so ignored it, leader=0
Received Message(uuid=UUID('e2f044bf-8dab-4384-ac13-708494f0ea8d'), flag=0), equal,leader=e2f044bf-8dab-4384-ac13-708494f0ea8d
Sent Message(uuid=UUID('e2f044bf-8dab-4384-ac13-708494f0ea8d'), flag=1)
Received Message(uuid=UUID('e2f044bf-8dab-4384-ac13-708494f0ea8d'), flag=1), equal,leader=e2f044bf-8dab-4384-ac13-708494f0ea8d
➜  pa1 (main) cat ./log2.txt                                                  ✗ ✭ ✱
Log for dcd941ad-6bb9-4ed5-86a9-649c2b980f3c
Received Message(uuid=UUID('e2f044bf-8dab-4384-ac13-708494f0ea8d'), flag=0), greater, leader=0
Sent Message(uuid=UUID('e2f044bf-8dab-4384-ac13-708494f0ea8d'), flag=0)
Received Message(uuid=UUID('e2f044bf-8dab-4384-ac13-708494f0ea8d'), flag=1), greater, leader=e2f044bf-8dab-4384-ac13-708494f0ea8d
Sent Message(uuid=UUID('e2f044bf-8dab-4384-ac13-708494f0ea8d'), flag=1)
➜  pa1 (main) cat ./log3.txt                                                  ✗ ✭ ✱
Log for 0c7bcbb0-b9ea-439e-aa91-f8b7afb45139
Received Message(uuid=UUID('dcd941ad-6bb9-4ed5-86a9-649c2b980f3c'), flag=0), greater, leader=0
Received Message(uuid=UUID('e2f044bf-8dab-4384-ac13-708494f0ea8d'), flag=0), greater, leader=0
Sent Message(uuid=UUID('dcd941ad-6bb9-4ed5-86a9-649c2b980f3c'), flag=0)
Sent Message(uuid=UUID('e2f044bf-8dab-4384-ac13-708494f0ea8d'), flag=0)
Received Message(uuid=UUID('e2f044bf-8dab-4384-ac13-708494f0ea8d'), flag=1), greater, leader=e2f044bf-8dab-4384-ac13-708494f0ea8d
Sent Message(uuid=UUID('e2f044bf-8dab-4384-ac13-708494f0ea8d'), flag=1)
```
