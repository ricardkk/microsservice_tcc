#!/bin/sh
set -eu
workspace_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "${1:-}" in
    non_centralized|centralized) environment_name=$1; shift ;;
    *) echo "Uso: $0 {non_centralized|centralized} <comando docker compose>" >&2; exit 2 ;;
esac
cd "$workspace_directory/$environment_name"
exec docker compose "$@"
