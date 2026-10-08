#!/usr/bin/env python3
"""Attach infrastructure checks to the shared experiment runner."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import observability
import runner


def before(args, compose):
    print("Verificando Fluent Bit, Loki, Grafana e provisioning.", flush=True)
    try:
        observability.Client.from_containers().ready(args.ready_timeout)
    except observability.CheckError as error:
        raise runner.ExperimentError(str(error)) from error


def after(args, compose, metadata, directory):
    print("Confirmando entrega do trace ao Loki após a restauração.", flush=True)
    return observability.Client.from_containers().wait_trace(metadata, args.ready_timeout, directory / "logs")


def reset(args, compose):
    compose.command("up", "--no-build", "-d", "--wait", "--wait-timeout", str(args.ready_timeout),
                    "loki", "fluent-bit", "grafana", timeout=args.ready_timeout + 30)
    before(args, compose)


if __name__ == "__main__":
    sys.exit(runner.main(before=before, after=after, reset=reset))
