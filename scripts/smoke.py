#!/usr/bin/env python3
"""Exercise the distributed flow with only the Python standard library."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser(description="Verifica o fluxo e as falhas da base do TCC")
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--faults", action="store_true", help="Exige FAULT_ENABLED=true nos serviços")
    parser.add_argument("--check-logs", action="store_true", help="Verifica correlação nos logs via Docker Compose")
    args = parser.parse_args()
    trace_prefix = "smoke-" + uuid.uuid4().hex[:12]
    results = []

    def call(method, path, payload=None, expected=200, fault=None, trace=None):
        trace = trace or trace_prefix + "-" + str(len(results))
        headers = {"Content-Type": "application/json", "X-Trace-Id": trace}
        if fault:
            headers.update({"X-Fault-Service": fault[0], "X-Fault-Type": fault[1]})
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(args.url.rstrip("/") + "/api" + path, data=data, headers=headers, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = json.loads(response.read())
            assert response.status == expected, f"{method} {path}: HTTP {response.status}, esperado {expected}: {body}"
            assert response.headers.get("X-Trace-Id") == trace, "traceId não foi preservado"
            if expected >= 400:
                assert body["traceId"] == trace, "Corpo do erro perdeu traceId"
        results.append({"method": method, "path": path, "status": expected, "traceId": trace, "fault": fault, "errorCode": body.get("code") if isinstance(body, dict) else None})
        return body

    user = call("POST", "/users", {"name": "Usuário experimental", "email": trace_prefix + "@example.com"}, 201)
    product = call("POST", "/products", {"name": "Produto experimental", "description": "Smoke test", "price": 19.95, "stock": 10}, 201)
    payload = {"userId": user["id"], "items": [{"productId": product["id"], "quantity": 2}]}
    distributed_trace = trace_prefix + "-distributed"
    order = call("POST", "/orders", payload, 201, trace=distributed_trace)
    assert Decimal(str(order["total"])) == Decimal("39.90")
    assert order["status"] == "CREATED"
    assert len(order["items"]) == 1
    assert call("GET", "/orders/" + str(order["id"]))["id"] == order["id"]
    call("GET", "/users/" + str(user["id"]))
    assert call("GET", "/products/" + str(product["id"]) + "/availability")["stock"] == 10
    call("GET", "/products")
    call("POST", "/orders", {"userId": user["id"], "items": []}, 400)
    call("POST", "/orders", {"userId": user["id"], "items": [{"productId": product["id"], "quantity": 11}]}, 422)
    call("POST", "/orders", {"userId": 9223372036854775807, "items": payload["items"]}, 422)
    call("GET", "/orders/9223372036854775807", expected=404)
    if args.faults:
        for fault_type, status in [("internal-error", 502), ("database", 502), ("timeout", 504), ("not-found", 422), ("invalid-response", 502)]:
            call("POST", "/orders", payload, status, ("product-service", fault_type))
        for fault_type, status in [("internal-error", 500), ("database", 503), ("timeout", 504)]:
            call("POST", "/orders", payload, status, ("order-service", fault_type))
    assert len(call("GET", "/orders?userId=" + str(user["id"]))) == 1, "Falha persistiu pedido parcial"
    if args.check_logs:
        repo = Path(__file__).resolve().parents[1]
        for service in ["gateway", "order-service", "user-service", "product-service"]:
            output = subprocess.check_output(["docker", "compose", "logs", "--no-color", "--no-log-prefix", service], cwd=repo, text=True)
            entries = []
            for line in output.splitlines():
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("traceId") == distributed_trace:
                    entries.append(entry)
            assert entries, f"traceId ausente em {service}"
            for entry in entries:
                assert all(key in entry for key in ["timestamp", "level", "service", "traceId", "operation", "message"]), entry
                assert entry["service"] == service
    print(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "checks": len(results), "logCorrelationChecked": args.check_logs, "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
