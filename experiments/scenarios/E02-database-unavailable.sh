#!/bin/sh
set -eu
scenario_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$scenario_directory/../run-experiment.sh" E02 "$@"
