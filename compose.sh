#!/bin/bash

composeFiles=("-f compose.yml")
remainingArgs=()

while [ $# -gt 0 ]; do
    case $1 in
    -e | --env)
        composeFiles+=("-f compose.$2.yml")
        shift
        ;;
    --email)
        composeFiles+=("-f compose.email.yml")
        ;;
    -h | --help)
        # Display script help information# Display script help information
        ;;
    -v | --verbose)
        # Enable verbose mode
        ;;
    *)
        remainingArgs+=" $1"
        ;;
    esac
    shift
done

docker compose ${composeFiles[@]} up $remainingArgs
