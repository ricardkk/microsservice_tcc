#!/usr/bin/env python3
"""Execute one controlled fault. No log interpretation or human diagnosis."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
APPS = ("gateway", "order-service", "user-service", "product-service")
DATABASES = ("users-db", "products-db", "orders-db")
SCENARIOS = {
    "E01": {"name": "Invalid request", "targetService": "order-service", "status": 400, "code": "VALIDATION_ERROR"},
    "E02": {"name": "Database unavailable", "targetService": "product-service", "resource": "products-db", "status": 502, "code": "DOWNSTREAM_ERROR"},
    "E03": {"name": "Service timeout", "targetService": "product-service", "fault": "timeout", "status": 504, "code": "DOWNSTREAM_TIMEOUT"},
    "E04": {"name": "Internal error", "targetService": "product-service", "fault": "internal-error", "status": 502, "code": "DOWNSTREAM_ERROR"},
    "E05": {"name": "Service unavailable", "targetService": "product-service", "resource": "product-service", "status": 502, "code": "DOWNSTREAM_UNAVAILABLE"},
}


class ExperimentError(Exception):
    pass


class InvariantViolation(ExperimentError):
    pass


class Interrupted(ExperimentError):
    def __init__(self, signum):
        self.signum = signum
        super().__init__(f"Execução interrompida por {signal.Signals(signum).name}")


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@contextmanager
def environment_lock():
    # Fixed location: --results-dir must not allow two runners on the same stack.
    directory = ROOT / "experiments/results"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".environment.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ExperimentError("Outro experimento ou reset está em execução.") from error
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


@contextmanager
def signal_handlers(cleanup=False):
    def interrupt(signum, frame):
        raise Interrupted(signum)

    previous = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.signal(signum, signal.SIG_IGN if cleanup else interrupt)
    try:
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


class Compose:
    def command(self, *arguments, timeout=15, environment=None, docker=False):
        command = ["docker"] + ([] if docker else ["compose"]) + list(arguments)
        try:
            result = subprocess.run(command, cwd=ROOT, env={**os.environ, **(environment or {})},
                                    text=True, capture_output=True, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ExperimentError(f"Falha ao executar {' '.join(command)}: {error}") from error
        if result.returncode:
            message = (result.stderr or result.stdout).strip()[-2000:]
            raise ExperimentError(f"{' '.join(command)}: {message}")
        return result.stdout

    def containers(self):
        identifiers = self.command("ps", "--all", "--quiet").split()
        if not identifiers:
            raise ExperimentError("Containers ausentes. Execute docker compose up --build -d --wait.")
        inspected = json.loads(self.command("inspect", *identifiers, docker=True))
        containers = {}
        for container in inspected:
            name = container["Config"].get("Labels", {}).get("com.docker.compose.service")
            if name in APPS + DATABASES:
                containers[name] = container
        missing = set(APPS + DATABASES) - containers.keys()
        if missing:
            raise ExperimentError(f"Containers ausentes: {', '.join(sorted(missing))}.")
        return containers

    def assert_ready(self):
        containers = self.containers()
        unavailable = [name for name, container in containers.items()
                       if not container["State"].get("Running")
                       or container["State"].get("Health", {}).get("Status") != "healthy"]
        if unavailable:
            raise ExperimentError(f"Ambiente indisponível: {', '.join(sorted(unavailable))}.")
        return containers

    def wait_ready(self, timeout):
        deadline = time.monotonic() + timeout
        while True:
            try:
                return self.assert_ready()
            except ExperimentError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(min(1, max(0, deadline - time.monotonic())))

    def start(self, resources, timeout):
        self.command("start", "--wait", "--wait-timeout", str(timeout), *resources, timeout=timeout + 15)


def http_call(url, method, path, payload=None, headers=None, timeout=15):
    outgoing = {"Content-Type": "application/json", **(headers or {})}
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url.rstrip("/") + path, data=data, headers=outgoing, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        response = error  # Expected 4xx/5xx must still be recorded and cleaned up.
    except (OSError, urllib.error.URLError) as error:
        raise ExperimentError(f"Falha na requisição {method} {path}: {error}") from error
    with response:
        raw = response.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = None
        return {"status": response.status, "traceId": response.headers.get("X-Trace-Id"),
                "contentType": response.headers.get("Content-Type"), "body": body, "rawBody": raw}


def require_response(response, status, context):
    if response["status"] != status or response["body"] is None:
        raise ExperimentError(f"{context}: HTTP {response['status']}, esperado {status}: {response['rawBody'][:500]}")
    return response["body"]


def settings(containers, args, scenario):
    def env(service):
        return dict(item.split("=", 1) for item in containers[service]["Config"].get("Env", []) if "=" in item)

    product, order, gateway = (env(name) for name in ("product-service", "order-service", "gateway"))
    values = {"databaseConnectionMs": int(product.get("DB_CONNECTION_TIMEOUT_MS", "1000")),
              "orderReadMs": int(order.get("HTTP_READ_TIMEOUT_MS", "2000")),
              "gatewayReadMs": int(gateway.get("HTTP_READ_TIMEOUT_MS", "10000")),
              "faultDelayMs": int(product.get("FAULT_DELAY_MS", "5000")),
              "requestMs": int(args.request_timeout * 1000)}
    if not (250 <= values["databaseConnectionMs"] < values["orderReadMs"] < values["gatewayReadMs"] < values["requestMs"]):
        raise ExperimentError("Configure banco < HTTP Order < HTTP Gateway < executor (padrão: 1000 < 2000 < 10000 < 15000 ms).")
    if scenario.get("fault") and product.get("FAULT_ENABLED", "false").lower() != "true":
        raise ExperimentError("E03/E04 exigem FAULT_ENABLED=true no Product. Execute FAULT_ENABLED=true docker compose up -d --wait.")
    if scenario.get("fault") == "timeout" and not (values["orderReadMs"] < values["faultDelayMs"] <= 60000):
        raise ExperimentError("FAULT_DELAY_MS deve superar a espera HTTP do Order e ser no máximo 60000.")
    return values


def wait_until(deadline):
    while time.monotonic() < deadline:
        time.sleep(max(0, min(0.25, deadline - time.monotonic())))


def prepare_fixtures(args, run_id, metadata):
    def call(method, path, payload=None, expected=200):
        response = http_call(args.url, method, path, payload, timeout=args.request_timeout)
        return require_response(response, expected, f"Preparação {method} {path}")

    call("GET", "/actuator/health")
    user = call("POST", "/api/users", {"name": "Usuário experimental", "email": run_id + "@example.com"}, 201)
    metadata["fixtures"] = {"userId": user["id"]}
    product = call("POST", "/api/products", {"name": "Produto experimental", "description": "Dados de preparação",
                                             "price": 19.95, "stock": 10}, 201)
    fixtures = metadata["fixtures"]
    fixtures["productId"] = product["id"]
    call("GET", f"/api/users/{user['id']}")
    product = call("GET", f"/api/products/{product['id']}")
    fixtures["initialStock"] = product["stock"]
    fixtures["ordersBefore"] = [order["id"] for order in call("GET", f"/api/orders?userId={user['id']}")]
    if product["stock"] < 1:
        raise ExperimentError("Produto de preparação sem estoque.")
    return {"userId": user["id"], "items": [{"productId": product["id"], "quantity": 1}]}


def verify_restored(args, metadata):
    require_response(http_call(args.url, "GET", "/actuator/health", timeout=args.request_timeout), 200, "Health após restauração")
    fixtures = metadata.get("fixtures", {})
    if "ordersBefore" not in fixtures:
        return
    orders = require_response(http_call(args.url, "GET", f"/api/orders?userId={fixtures['userId']}", timeout=args.request_timeout), 200, "Pedidos após restauração")
    product = require_response(http_call(args.url, "GET", f"/api/products/{fixtures['productId']}", timeout=args.request_timeout), 200, "Produto após restauração")
    fixtures["ordersAfter"] = [order["id"] for order in orders]
    fixtures["stockAfter"] = product["stock"]
    if fixtures["ordersAfter"] != fixtures["ordersBefore"] or fixtures["stockAfter"] != fixtures["initialStock"]:
        raise InvariantViolation("Invariante violada: a requisição de falha persistiu pedido ou alterou estoque.")


def collect_logs(compose, directory, metadata):
    logs = directory / "logs"
    logs.mkdir(exist_ok=True)
    errors = {}
    for service in APPS:
        try:
            output = compose.command("logs", "--no-color", "--no-log-prefix", "--since", metadata["requestStartedAt"], service)
            (logs / f"{service}.log").write_text(output, encoding="utf-8")
        except ExperimentError as error:
            errors[service] = str(error)
    metadata["logsCollectedAt"] = timestamp()
    metadata["logCollection"] = {"success": not errors, "errors": errors}
    if errors:
        raise ExperimentError("Falha na coleta de logs; consulte metadata.json.")


def run_experiment(args, compose):
    scenario = SCENARIOS[args.scenario]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    directory = args.results_dir / args.scenario / run_id
    directory.mkdir(parents=True)
    metadata = {"runId": run_id, "scenario": args.scenario, "name": scenario["name"],
                "targetService": scenario["targetService"], "targetResource": scenario.get("resource"),
                "startedAt": timestamp(), "baseUrl": args.url, "success": False,
                "expectedResponse": {"status": scenario["status"], "code": scenario["code"]}}
    resource = None
    pending_until = 0
    ready = False
    exit_code = 1
    write_json(directory / "metadata.json", metadata)
    try:
        compose.command("version")
        containers = compose.assert_ready()  # Abort; do not silently repair an invalid baseline.
        ready = True
        metadata["timeouts"] = settings(containers, args, scenario)
        metadata["images"] = {name: container.get("Image") for name, container in containers.items()}
        print(f"{args.scenario}: ambiente validado; preparando dados.", flush=True)
        payload = prepare_fixtures(args, run_id, metadata)
        if args.scenario == "E01":
            payload["items"][0]["quantity"] = -5
        headers = {}
        if scenario.get("fault"):
            headers = {"X-Fault-Service": scenario["targetService"], "X-Fault-Type": scenario["fault"]}
        metadata["request"] = {"method": "POST", "path": "/api/orders", "payload": payload, "headers": headers}
        write_json(directory / "metadata.json", metadata)
        if scenario.get("resource"):
            # Arm cleanup before stop: timeout/interruption may happen after Docker stops it.
            resource = scenario["resource"]
            print(f"Parando {resource}.", flush=True)
            metadata["injectionStartedAt"] = timestamp()
            compose.command("stop", "--timeout", "5", resource, timeout=30)
            metadata["injectionCompletedAt"] = timestamp()
        metadata["requestStartedAt"] = timestamp()
        print("Executando POST /api/orders.", flush=True)
        if args.scenario == "E03":
            # Includes allowance for the earlier User call before Product receives the GET.
            pending_until = time.monotonic() + (metadata["timeouts"]["faultDelayMs"] + metadata["timeouts"]["orderReadMs"]) / 1000 + 1
        response = http_call(args.url, "POST", "/api/orders", payload, headers, args.request_timeout)
        metadata["requestCompletedAt"] = timestamp()
        metadata["traceId"] = response["traceId"]
        metadata["observedResponse"] = {"status": response["status"], "code": (response["body"] or {}).get("code") if isinstance(response["body"], dict) else None}
        write_json(directory / "response.json", response)
        print(f"HTTP {response['status']} recebido; aguardando conclusão e coletando logs.", flush=True)
        wait_until(pending_until)
        collect_logs(compose, directory, metadata)
        trace = response["traceId"] or ""
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", trace) or not isinstance(response["body"], dict) or response["body"].get("traceId") != trace:
            raise ExperimentError("Resposta sem traceId válido gerado/preservado pela aplicação.")
        if metadata["observedResponse"] != metadata["expectedResponse"]:
            raise ExperimentError(f"Resposta observada {metadata['observedResponse']}; esperada {metadata['expectedResponse']}.")
        metadata["success"] = True
        exit_code = 0
    except (Exception, KeyboardInterrupt) as error:
        metadata["error"] = str(error) or "Execução interrompida"
        exit_code = 128 + error.signum if isinstance(error, Interrupted) else 1
    finally:
        # A second Ctrl+C must not interrupt the bounded restoration.
        with signal_handlers(cleanup=True):
            try:
                wait_until(pending_until)
                if metadata.get("requestStartedAt") and "logCollection" not in metadata:
                    try:
                        collect_logs(compose, directory, metadata)
                    except Exception as error:
                        metadata.setdefault("error", str(error))
                        metadata.setdefault("logCollection", {"success": False, "errors": {"collection": str(error)}})
                        metadata["success"] = False
                        exit_code = 1
                if resource:
                    print(f"Restaurando {resource}.", flush=True)
                    compose.start([resource], args.ready_timeout)
                if ready:
                    compose.wait_ready(args.ready_timeout)
                    try:
                        verify_restored(args, metadata)
                        metadata["invariants"] = {"success": True}
                    except InvariantViolation as error:
                        metadata["invariants"] = {"success": False, "error": str(error)}
                        metadata.setdefault("error", str(error))
                        metadata["success"] = False
                        exit_code = 1
                metadata["cleanup"] = {"success": True, "resource": resource, "completedAt": timestamp()}
            except (Exception, KeyboardInterrupt) as error:
                metadata["cleanup"] = {"success": False, "resource": resource, "error": str(error), "completedAt": timestamp()}
                metadata["success"] = False
                exit_code = 1
            metadata["finishedAt"] = timestamp()
            write_json(directory / "metadata.json", metadata)
    print(f"{args.scenario}: {'concluído' if metadata['success'] else 'falhou'}. Resultados: {directory}")
    if metadata.get("error"):
        print(metadata["error"], file=sys.stderr)
    if not metadata["cleanup"]["success"]:
        print("Restauração falhou. Execute experiments/reset-environment.sh. " + metadata["cleanup"]["error"], file=sys.stderr)
    return exit_code


def reset_environment(args, compose):
    compose.start(DATABASES, args.ready_timeout)
    compose.command("up", "--no-build", "--no-deps", "-d", "--wait", "--wait-timeout", str(args.ready_timeout),
                    *APPS, timeout=args.ready_timeout + 30, environment={"FAULT_ENABLED": "false"})
    compose.wait_ready(args.ready_timeout)
    for path in ("/actuator/health", "/api/users", "/api/products", "/api/orders"):
        require_response(http_call(args.url, "GET", path, timeout=args.request_timeout), 200, "Reset " + path)
    print("Ambiente restaurado; injeção desabilitada nos processos. Dados e resultados preservados.")


def main():
    parser = argparse.ArgumentParser(description="Executa um cenário controlado e restaura o ambiente")
    parser.add_argument("scenario", choices=(*SCENARIOS, "reset"))
    parser.add_argument("--url", default="http://localhost:8080", help="Gateway do mesmo projeto Compose")
    parser.add_argument("--ready-timeout", type=int, default=90, help="Prazo em segundos para restauração")
    parser.add_argument("--request-timeout", type=float, default=15, help="Prazo HTTP do executor em segundos")
    parser.add_argument("--results-dir", type=Path, default=ROOT / "experiments/results")
    args = parser.parse_args()
    if args.ready_timeout <= 0 or args.request_timeout <= 0 or not args.url.startswith(("http://", "https://")):
        parser.error("Prazos devem ser positivos e a URL deve começar com http:// ou https://.")
    try:
        with environment_lock(), signal_handlers():
            compose = Compose()
            if args.scenario == "reset":
                reset_environment(args, compose)
                return 0
            return run_experiment(args, compose)
    except (ExperimentError, KeyboardInterrupt, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 128 + error.signum if isinstance(error, Interrupted) else 1


if __name__ == "__main__":
    sys.exit(main())
