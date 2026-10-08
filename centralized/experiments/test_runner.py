"""Exercise real HTTP recording and failure cleanup without requiring Docker."""
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import signal
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import runner


class Api(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def respond(self, status, body):
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("X-Trace-Id", "application-generated-trace")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/actuator/health":
            body = {"status": "UP"}
        elif self.path.startswith("/api/users/"):
            body = {"id": 42}
        elif self.path.startswith("/api/products/"):
            if self.server.requests:
                self.server.recovery_reads += 1
                if self.server.product_failures:
                    self.server.product_failures -= 1
                    self.respond(503, {"code": "DATABASE_UNAVAILABLE"})
                    return
            body = {"id": 71, "stock": 10}
        elif self.path.startswith("/api/orders"):
            body = self.server.orders
        else:
            self.respond(404, {})
            return
        self.respond(200, body)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/users":
            self.respond(201, {"id": 42})
        elif self.path == "/api/products":
            self.respond(201, {"id": 71, "stock": 10})
        elif self.path == "/api/orders":
            self.server.requests.append({"payload": body, "traceId": self.headers.get("X-Trace-Id"),
                                         "fault": self.headers.get("X-Fault-Type")})
            if self.server.persist:
                self.server.orders.append({"id": 99})
            expected = runner.SCENARIOS[self.server.scenario]
            self.respond(self.server.status or expected["status"],
                         {"code": expected["code"], "traceId": "application-generated-trace"})


class FakeCompose:
    def __init__(self):
        self.stopped = []
        self.started = []
        self.fail_stop = False
        self.fail_start = False
        self.fail_logs = False
        self.ready = True
        self.enabled = True

    def command(self, *arguments, **kwargs):
        if arguments[0] == "stop":
            self.stopped.append(arguments[-1])
            if self.fail_stop:
                raise runner.Interrupted(signal.SIGINT)
        if arguments[0] == "logs":
            if self.fail_logs:
                raise runner.ExperimentError("Coleta indisponível")
            return '{"traceId":"application-generated-trace","message":"Operational error"}\n'
        return ""

    def assert_ready(self):
        if not self.ready:
            raise runner.ExperimentError("Ambiente indisponível")
        return {name: {"Config": {"Env": ["FAULT_ENABLED=" + str(self.enabled).lower(), "HTTP_READ_TIMEOUT_MS=" + ("10000" if name == "gateway" else "2000")]}}
                for name in runner.APPS + runner.DATABASES}

    def wait_ready(self, timeout):
        return self.assert_ready()

    def start(self, resources, timeout):
        self.started.extend(resources)
        if self.fail_start:
            raise runner.ExperimentError("Não foi possível iniciar")


class RunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = ThreadingHTTPServer(("127.0.0.1", 0), Api)
        cls.thread = threading.Thread(target=cls.api.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.api.shutdown()
        cls.api.server_close()
        cls.thread.join()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.args = SimpleNamespace(scenario="E02", url=f"http://127.0.0.1:{self.api.server_port}",
                                    ready_timeout=1, request_timeout=15, results_dir=Path(self.temporary.name))
        self.compose = FakeCompose()
        self.api.scenario = "E02"
        self.api.orders = []
        self.api.requests = []
        self.api.status = None
        self.api.persist = False
        self.api.product_failures = 0
        self.api.recovery_reads = 0

    def execute(self, scenario="E02", after=None):
        self.args.scenario = self.api.scenario = scenario
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), patch.object(runner, "wait_until"):
            code = runner.run_experiment(self.args, self.compose, after=after)
        directories = sorted((self.args.results_dir / scenario).iterdir())
        directory = directories[-1]
        return code, json.loads((directory / "metadata.json").read_text()), directory

    def test_each_scenario_records_http_errors_and_application_trace(self):
        for scenario in runner.SCENARIOS:
            with self.subTest(scenario=scenario):
                code, metadata, directory = self.execute(scenario)
                self.assertEqual(code, 0)
                self.assertTrue(metadata["success"])
                self.assertTrue(metadata["cleanup"]["success"])
                self.assertEqual(metadata["traceId"], "application-generated-trace")
                response = json.loads((directory / "response.json").read_text())
                self.assertEqual(response["status"], runner.SCENARIOS[scenario]["status"])
                request = self.api.requests[-1]
                self.assertIsNone(request["traceId"])
                self.assertEqual(request["payload"]["userId"], 42)
                self.assertEqual(request["payload"]["items"][0]["productId"], 71)
                self.assertEqual(request["payload"]["items"][0]["quantity"], -5 if scenario == "E01" else 1)
                self.assertEqual(request["fault"], runner.SCENARIOS[scenario].get("fault"))
                self.assertEqual(len(list((directory / "logs").glob("*.log"))), 4)

    def test_stop_interrupted_after_side_effect_still_restores_database(self):
        self.compose.fail_stop = True
        code, metadata, _ = self.execute()
        self.assertEqual(code, 130)
        self.assertEqual(self.compose.started, ["products-db"])
        self.assertTrue(metadata["cleanup"]["success"])
        self.assertFalse(metadata["success"])
        self.assertFalse(self.api.requests)

    def test_connection_failure_still_restores_stopped_service(self):
        original = runner.http_call

        def fail_request(url, method, path, *args, **kwargs):
            if method == "POST" and path == "/api/orders":
                raise runner.ExperimentError("Conexão perdida")
            return original(url, method, path, *args, **kwargs)

        with patch.object(runner, "http_call", side_effect=fail_request):
            code, metadata, _ = self.execute("E05")
        self.assertEqual(code, 1)
        self.assertEqual(self.compose.started, ["product-service"])
        self.assertTrue(metadata["cleanup"]["success"])
        self.assertIn("Conexão perdida", metadata["error"])

    def test_log_io_error_does_not_prevent_restoration(self):
        with patch.object(runner, "collect_logs", side_effect=OSError("Disco indisponível")):
            code, metadata, _ = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(self.compose.started, ["products-db"])
        self.assertTrue(metadata["cleanup"]["success"])
        self.assertFalse(metadata["logCollection"]["success"])

    def test_cleanup_failure_and_unexpected_http_are_both_preserved(self):
        self.api.status = 200
        self.compose.fail_start = True
        code, metadata, directory = self.execute()
        self.assertEqual(code, 1)
        self.assertFalse(metadata["cleanup"]["success"])
        self.assertEqual(metadata["observedResponse"]["status"], 200)
        self.assertEqual(json.loads((directory / "response.json").read_text())["status"], 200)
        self.assertIn("Resposta observada", metadata["error"])

    def test_persisted_order_fails_invariant_without_claiming_stack_restore_failed(self):
        self.api.persist = True
        with patch.object(runner.time, "sleep") as sleep:
            code, metadata, _ = self.execute()
        sleep.assert_not_called()
        self.assertEqual(code, 1)
        self.assertFalse(metadata["invariants"]["success"])
        self.assertTrue(metadata["cleanup"]["success"])
        self.assertEqual(metadata["fixtures"]["ordersAfter"], [99])

    def test_product_recovers_after_healthy_container_and_temporary_503(self):
        self.api.product_failures = 2
        with patch.object(runner.time, "sleep"):
            code, metadata, directory = self.execute()
        self.assertEqual(code, 0)
        self.assertEqual(self.api.recovery_reads, 3)
        self.assertEqual(len(self.api.requests), 1)
        self.assertEqual(metadata["observedResponse"]["status"], 502)
        self.assertEqual(json.loads((directory / "response.json").read_text())["status"], 502)
        self.assertTrue(metadata["cleanup"]["success"])
        self.assertTrue(metadata["invariants"]["success"])
        self.assertEqual(metadata["fixtures"]["stockAfter"], 10)

    def test_product_recovery_timeout_preserves_failure_response(self):
        self.api.product_failures = 1000
        self.args.ready_timeout = .05
        code, metadata, directory = self.execute()
        self.assertEqual(code, 1)
        self.assertFalse(metadata["cleanup"]["success"])
        self.assertIn("Recuperação funcional não concluída", metadata["cleanup"]["error"])
        self.assertIn("HTTP 503", metadata["cleanup"]["error"])
        self.assertEqual(len(self.api.requests), 1)
        self.assertEqual(json.loads((directory / "response.json").read_text())["status"], 502)

    def test_unready_environment_aborts_before_creating_data_or_stopping_resources(self):
        self.compose.ready = False
        code, metadata, _ = self.execute()
        self.assertEqual(code, 1)
        self.assertNotIn("fixtures", metadata)
        self.assertFalse(self.compose.stopped)
        self.assertFalse(self.compose.started)

    def test_disabled_hooks_abort_before_fixture_creation(self):
        self.compose.enabled = False
        code, metadata, _ = self.execute("E03")
        self.assertEqual(code, 1)
        self.assertNotIn("fixtures", metadata)
        self.assertIn("FAULT_ENABLED", metadata["error"])

    def test_repetitions_do_not_overwrite_results(self):
        _, _, first = self.execute()
        _, _, second = self.execute()
        self.assertNotEqual(first, second)
        self.assertTrue((first / "metadata.json").exists())

    def test_observability_failure_is_reported_after_resource_restoration(self):
        def verify(args, compose, metadata, directory):
            self.assertEqual(compose.started, ["products-db"])
            self.assertTrue(metadata["cleanup"]["success"])
            raise runner.ExperimentError("Loki indisponível")

        code, metadata, _ = self.execute(after=verify)
        self.assertEqual(code, 1)
        self.assertTrue(metadata["cleanup"]["success"])
        self.assertFalse(metadata["observability"]["success"])
        self.assertFalse(metadata["success"])

    def test_signal_during_delivery_check_preserves_exit_status_and_restoration(self):
        def verify(args, compose, metadata, directory):
            self.assertEqual(compose.started, ["products-db"])
            raise runner.Interrupted(signal.SIGTERM)

        code, metadata, _ = self.execute(after=verify)
        self.assertEqual(code, 128 + signal.SIGTERM)
        self.assertTrue(metadata["cleanup"]["success"])
        self.assertFalse(metadata["observability"]["success"])

    def test_lock_is_shared_even_when_results_directory_changes(self):
        with patch.object(runner, "ROOT", Path(self.temporary.name)):
            with runner.environment_lock():
                with self.assertRaises(runner.ExperimentError):
                    with runner.environment_lock():
                        self.fail("A segunda execução obteve o lock")


if __name__ == "__main__":
    unittest.main()
