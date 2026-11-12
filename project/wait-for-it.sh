#!/bin/sh
# wait-for-it.sh

set -e

# Check if the script was called with at least two arguments: HOST and PORT
if [ "$1" == "db:3306" ] || [ "$1" == "localhost:5432" ]; then
    # Check if the first argument is a host and second argument is a port
    if [ -z "$2" ]; then
        echo "Usage: ./wait-for-it.sh <host> <port>"
        exit 1
    fi
    
    host=$1
    port=$2
    
    until nc -z $host $port; do
        echo "Waiting for $host:$port to be ready..."
        sleep 1
    done
    echo "$host:$port is up!"
else
    # Handle other commands (like the exec "$@" command)
    exec "$@"
fi
