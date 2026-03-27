import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.responses import JSONResponse

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.api.routes.ops import liveness_payload, readiness_payload
from app.main import request_context_middleware
from app.observability import (
    clear_metrics,
    clear_request_id,
    get_request_id,
    increment_counter,
    normalize_reason_label,
    normalize_tracking_phone,
    observe_duration,
    render_metrics,
    should_track_phone,
)


class FakeRequest:
    def __init__(self, path: str = "/healthz", method: str = "GET", headers: dict | None = None):
        self.method = method
        self.headers = headers or {}
        self.url = SimpleNamespace(path=path)


class ObservabilityHardeningTests(unittest.TestCase):
    def setUp(self):
        clear_metrics()
        clear_request_id()

    def test_liveness_payload_is_ok(self):
        self.assertEqual(liveness_payload(), {"status": "ok"})

    def test_readiness_payload_reports_database_up(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "chokobot.db")
            with patch.dict(os.environ, {"DB_PATH": db_path}, clear=False):
                payload, status_code = readiness_payload()

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["checks"]["database"], "up")

    def test_readiness_payload_reports_database_down(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "missing-dir", "chokobot.db")
            with patch.dict(os.environ, {"DB_PATH": db_path}, clear=False):
                payload, status_code = readiness_payload()

        self.assertEqual(status_code, 503)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["checks"]["database"], "down")

    def test_metrics_render_counters_and_histograms(self):
        increment_counter("demo_counter_total", route="/x")
        observe_duration("demo_latency_seconds", 0.5, route="/x")
        rendered = render_metrics()

        self.assertIn('demo_counter_total{route="/x"} 1.0', rendered)
        self.assertIn('demo_latency_seconds_count{route="/x"} 1.0', rendered)
        self.assertIn('demo_latency_seconds_sum{route="/x"} 0.5', rendered)

    def test_request_context_middleware_sets_request_id_header(self):
        async def call_next(request):
            self.assertNotEqual(get_request_id(), "-")
            return JSONResponse({"status": "ok"})

        request = FakeRequest(path="/demo", headers={"X-Request-ID": "abc123"})
        response = asyncio.run(request_context_middleware(request, call_next))

        self.assertEqual(response.headers["X-Request-ID"], "abc123")
        self.assertEqual(get_request_id(), "-")
        rendered = render_metrics()
        self.assertIn('http_requests_total{method="GET",path="/demo",status_code="200"} 1.0', rendered)

    def test_should_track_phone_normalizes_known_test_number_variants(self):
        self.assertEqual(normalize_tracking_phone("+55 11 88888-8888@c.us"), "5511888888888")
        self.assertFalse(should_track_phone("+55 11 88888-8888"))
        self.assertFalse(should_track_phone("11888888888"))
        self.assertTrue(should_track_phone("5511999999999"))

    def test_should_track_phone_honors_env_test_phones(self):
        with patch.dict(os.environ, {"TEST_PHONES": "5511777777777"}, clear=False):
            self.assertFalse(should_track_phone("5511777777777"))
            self.assertTrue(should_track_phone("5511999999999"))

    def test_normalize_reason_label_formats_unknown_or_blank(self):
        self.assertEqual(normalize_reason_label("  pix_missing "), "pix_missing")
        self.assertEqual(normalize_reason_label(None), "unknown")
        self.assertEqual(normalize_reason_label("", default="fallback"), "fallback")


if __name__ == "__main__":
    unittest.main()
