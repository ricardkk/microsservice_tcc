from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlparse

import observability


class Api(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/ready":
            body = b"ready\n"
        elif self.path == "/api/v1/health":
            body = b"ok\n"
        elif self.path == "/api/health":
            body = b'{"database":"ok"}'
        elif self.path.startswith("/api/datasources/"):
            body = b'{"status":"OK"}'
        elif self.path.startswith("/api/dashboards/"):
            body = b'{"dashboard":{"uid":"tcc-logs"}}'
        else:
            self.server.last_query = parse_qs(urlparse(self.path).query).get("query", [""])[0]
            body = json.dumps({"status": "success", "data": {"result": self.server.streams}}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ObservabilityTest(unittest.TestCase):
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
        self.logs = Path(self.temporary.name)
        url = f"http://127.0.0.1:{self.api.server_port}"
        self.client = observability.Client({name: url for name in observability.PORTS})
        self.now = datetime.now(timezone.utc).isoformat()
        self.metadata = {"scenario": "E02", "traceId": "test-trace", "requestStartedAt": self.now,
                         "finishedAt": self.now, "logsCollectedAt": self.now}
        self.api.streams = []

    def emit(self, services, corrupt_stack=False):
        for service in services:
            entry = {"timestamp": self.now, "service": service, "level": "ERROR", "traceId": "test-trace",
                     "operation": "GET /products/42", "message": "Database operation failed", "stack_trace": "cause\n" + "detail" * 1000}
            (self.logs / f"{service}.log").write_text(json.dumps(entry) + "\n")
            transported = {**entry, "stream": "stdout"}
            if corrupt_stack:
                transported["stack_trace"] = "truncated"
            self.api.streams.append({"stream": {"job": "tcc", "service": service}, "values": [["1", json.dumps(transported)]]})

    def test_endpoints_and_all_original_fields_are_verified(self):
        self.emit(observability.ALL_APPS)
        self.client.ready(timeout=.01)
        result = self.client.wait_trace(self.metadata, .01, self.logs)
        self.assertEqual(result["sourceEventsVerified"], 4)
        self.assertEqual(result["events"], 4)

    def test_corrupted_stack_trace_is_detected_even_when_all_services_arrived(self):
        self.emit(observability.ALL_APPS, corrupt_stack=True)
        with self.assertRaisesRegex(observability.CheckError, "preservados: False"):
            self.client.wait_trace(self.metadata, .01, self.logs)

    def test_partial_delivery_cannot_pass(self):
        self.emit(observability.ALL_APPS)
        self.api.streams.pop()
        with self.assertRaises(observability.CheckError):
            self.client.wait_trace(self.metadata, .01, self.logs)

    def test_validation_and_stopped_service_use_their_actual_participants(self):
        for scenario in ("E01", "E05"):
            with self.subTest(scenario=scenario):
                self.api.streams = []
                self.metadata["scenario"] = scenario
                self.emit(observability.PARTICIPANTS[scenario])
                result = self.client.wait_trace(self.metadata, .01, self.logs)
                self.assertEqual(set(result["services"]), observability.PARTICIPANTS[scenario])

    def test_trace_id_label_is_rejected(self):
        self.emit(observability.ALL_APPS)
        self.api.streams[0]["stream"]["traceId"] = "test-trace"
        with self.assertRaisesRegex(observability.CheckError, "label"):
            self.client.wait_trace(self.metadata, .01, self.logs)

    def test_delivery_query_preserves_stored_labels_and_escapes_trace(self):
        self.metadata["traceId"] = "test.trace-1"
        self.emit(observability.ALL_APPS)
        for service in observability.ALL_APPS:
            path = self.logs / f"{service}.log"
            path.write_text(path.read_text().replace("test-trace", "test.trace-1"))
        for stream in self.api.streams:
            stream["values"][0][1] = stream["values"][0][1].replace("test-trace", "test.trace-1")
        self.client.wait_trace(self.metadata, .01, self.logs)
        query = self.api.last_query
        self.assertNotIn("| json", query)
        self.assertIn("|~", query)
        pattern = json.loads(query.split("|~", 1)[1].strip())
        self.assertRegex('{"traceId" : "test.trace-1"}', pattern)
        self.assertNotRegex('{"traceId":"testXtrace-1"}', pattern)


if __name__ == "__main__":
    unittest.main()
