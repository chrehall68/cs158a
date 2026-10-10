#!/bin/bash

machine_id=$(docker compose ps -q machine$1)
if [ -z "$machine_id" ]; then
    exit 1
fi
echo "Attaching to machine$1. Press enter to start. Press ctrl-c to exit."
docker attach --detach-keys="ctrl-c" $machine_id
exit 0