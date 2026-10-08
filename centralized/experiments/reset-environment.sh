#!/bin/sh
set -eu
experiment_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$experiment_directory/centralized_runner.py" reset "$@"
