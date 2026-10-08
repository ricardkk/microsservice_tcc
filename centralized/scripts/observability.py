#!/usr/bin/env python3
"""Check readiness and delivery of a trace; never diagnose the injected fault."""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PORTS = {"loki": 3100, "grafana": 3000, "fluent-bit": 2020}
PARTICIPANTS = {"E01": {"gateway", "order-service"}, "E05": {"gateway", "order-service", "user-service"}}
ALL_APPS = {"gateway", "order-service", "user-service", "product-service"}


class CheckError(Exception):
    pass


def request(url, auth=None):
    headers = {}
    if auth:
        headers["Authorization"] = "Basic " + base64.b64encode((auth[0] + ":" + auth[1]).encode()).decode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=5) as response:
            value = response.read().decode()
    except (OSError, urllib.error.URLError) as error:
        raise CheckError(f"Endpoint indisponível: {url}: {error}") from error
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value.strip()


def inspect_containers():
    def command(arguments):
        try:
            result = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise CheckError(f"Falha ao inspecionar containers: {error}") from error
        if result.returncode:
            raise CheckError(result.stderr.strip())
        return result.stdout
    ids = command(["docker", "compose", "ps", "--all", "--quiet"]).split()
    if not ids:
        raise CheckError("Containers ausentes; inicie o Compose centralized.")
    containers = json.loads(command(["docker", "inspect", *ids]))
    found = {item["Config"].get("Labels", {}).get("com.docker.compose.service"): item for item in containers}
    for service in PORTS:
        if service not in found or not found[service]["State"].get("Running"):
            raise CheckError(f"Container {service} indisponível.")
    return found


class Client:
    def __init__(self, urls=None, auth=None):
        self.urls = urls or {name: f"http://127.0.0.1:{port}" for name, port in PORTS.items()}
        self.auth = auth or (os.environ.get("GRAFANA_ADMIN_USER", "admin"), os.environ.get("GRAFANA_ADMIN_PASSWORD", "tcc-local"))

    @classmethod
    def from_containers(cls):
        containers = inspect_containers()
        urls = {}
        for service, port in PORTS.items():
            bindings = containers[service]["NetworkSettings"]["Ports"].get(f"{port}/tcp") or []
            if not bindings:
                raise CheckError(f"Porta HTTP de {service} não publicada no host.")
            urls[service] = "http://127.0.0.1:" + bindings[0]["HostPort"]
        env = dict(item.split("=", 1) for item in containers["grafana"]["Config"].get("Env", []) if "=" in item)
        return cls(urls, (env.get("GF_SECURITY_ADMIN_USER", "admin"), env.get("GF_SECURITY_ADMIN_PASSWORD", "tcc-local")))

    def ready(self, timeout=60):
        deadline = time.monotonic() + timeout
        while True:
            try:
                if request(self.urls["loki"] + "/ready") != "ready":
                    raise CheckError("Loki ainda não está pronto.")
                if request(self.urls["fluent-bit"] + "/api/v1/health") != "ok":
                    raise CheckError("Fluent Bit não está saudável.")
                if request(self.urls["grafana"] + "/api/health").get("database") != "ok":
                    raise CheckError("Grafana não está saudável.")
                health = request(self.urls["grafana"] + "/api/datasources/uid/tcc-loki/health", self.auth)
                if health.get("status") != "OK":
                    raise CheckError("Data Source Loki indisponível no Grafana.")
                dashboard = request(self.urls["grafana"] + "/api/dashboards/uid/tcc-logs", self.auth)
                if dashboard.get("dashboard", {}).get("uid") != "tcc-logs":
                    raise CheckError("Dashboard provisionado indisponível.")
                return
            except CheckError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(min(1, max(0, deadline - time.monotonic())))

    def wait_trace(self, metadata, timeout=60, logs_directory=None):
        trace = metadata.get("traceId", "")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", trace):
            raise CheckError("Metadados sem traceId válido.")
        start = datetime.fromisoformat(metadata["requestStartedAt"])
        end = datetime.fromisoformat(metadata.get("logsCollectedAt", metadata["finishedAt"]))
        # JSON parsing in LogQL adds extracted fields to the returned stream
        # labels. A line filter leaves only stored labels, so the check below
        # can distinguish indexed trace IDs from fields extracted at query time.
        pattern = r'"traceId"\s*:\s*"' + re.escape(trace) + '"'
        query = '{job="tcc"} |~ ' + json.dumps(pattern)
        parameters = urllib.parse.urlencode({"query": query, "start": str(int(start.timestamp() * 1e9) - 1000000000),
                                             "end": str(int(end.timestamp() * 1e9) + 1000000000), "limit": "5000", "direction": "forward"})
        expected = PARTICIPANTS.get(metadata["scenario"], ALL_APPS)
        original = []
        if logs_directory:
            for service in expected:
                for line in (logs_directory / f"{service}.log").read_text().splitlines():
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("traceId") == trace:
                        original.append(entry)
            if not original:
                raise CheckError("Logs locais não contêm eventos do trace para comparação.")
        deadline = time.monotonic() + timeout
        while True:
            data = request(self.urls["loki"] + "/loki/api/v1/query_range?" + parameters)
            if data.get("status") != "success":
                raise CheckError("Consulta Loki falhou.")
            found, count, events = set(), 0, []
            for stream in data["data"]["result"]:
                if "traceId" in stream["stream"]:
                    raise CheckError("traceId foi indexado como label.")
                for timestamp, line in stream["values"]:
                    entry = json.loads(line)
                    if not all(key in entry for key in ("timestamp", "level", "service", "traceId", "operation", "message")):
                        raise CheckError("Evento de requisição perdeu campos na centralização.")
                    if entry["traceId"] != trace:
                        raise CheckError("Consulta retornou trace diferente.")
                    found.add(entry["service"])
                    count += 1
                    events.append(entry)
            preserved = all(any(all(collected.get(key) == value for key, value in entry.items()) for collected in events) for entry in original)
            if expected <= found and preserved:
                return {"success": True, "traceId": trace, "services": sorted(found), "events": count,
                        "sourceEventsVerified": len(original),
                        "checkedAt": datetime.now(timezone.utc).isoformat()}
            if time.monotonic() >= deadline:
                raise CheckError("Logs incompletos no Loki; serviços ausentes: " + ", ".join(sorted(expected - found)) + "; campos/eventos preservados: " + str(preserved))
            time.sleep(min(1, max(0, deadline - time.monotonic())))


def main():
    parser = argparse.ArgumentParser(description="Verifica disponibilidade e entrega dos logs centralizados")
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--http-only", action="store_true", help="Verifica apenas HTTP, sem inspecionar containers")
    parser.add_argument("--loki-url", default="http://127.0.0.1:3100")
    parser.add_argument("--grafana-url", default="http://127.0.0.1:3000")
    parser.add_argument("--fluent-bit-url", default="http://127.0.0.1:2020")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("O prazo deve ser positivo.")
    try:
        client = Client({"loki": args.loki_url, "grafana": args.grafana_url, "fluent-bit": args.fluent_bit_url}) if args.http_only else Client.from_containers()
        client.ready(args.timeout)
        result = client.wait_trace(json.loads(args.metadata.read_text()), args.timeout, args.metadata.parent / "logs") if args.metadata else {"success": True}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (CheckError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
