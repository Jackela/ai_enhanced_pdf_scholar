import importlib.util
import json
import sys
import time
from pathlib import Path


def _load_module():
    module_name = "rate_limit_monitor_local"
    module_path = Path("backend/api/middleware/rate_limit_monitor.py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_rate_limit_monitor_metrics_and_alerts(tmp_path, caplog):
    rlm = _load_module()
    RateLimitMonitor = rlm.RateLimitMonitor
    RateLimitEvent = rlm.RateLimitEvent

    monitor = RateLimitMonitor(
        max_events=10,
        metrics_window_minutes=1,
        alert_threshold=0.5,
        log_file=None,
    )
    now = time.time()

    def _event(
        ip: str,
        endpoint: str,
        status: int,
        response_time: float = 0.1,
        ts: float | None = None,
    ):
        return RateLimitEvent(
            timestamp=ts or time.time(),
            client_ip=ip,
            endpoint=endpoint,
            status_code=status,
            response_time=response_time,
            user_agent="agent",
            limit_type="endpoint",
            limit_value=10,
            remaining=5,
        )

    # Record mixed events (200/429/error)
    monitor.record_event(_event("1.1.1.1", "/a", 200, ts=now - 10))
    monitor.record_event(_event("1.1.1.1", "/a", 429, ts=now - 9))
    monitor.record_event(_event("2.2.2.2", "/b", 500, ts=now - 5))
    monitor.record_event(_event("1.1.1.1", "/a", 429, ts=now - 4))
    monitor.record_event(_event("1.1.1.1", "/a", 429, ts=now - 3))

    metrics = monitor.get_metrics(window_minutes=1)
    assert metrics.total_requests == 5
    assert metrics.rate_limited_requests == 3
    assert metrics.error_requests == 1
    assert metrics.successful_requests == 1
    assert metrics.unique_ips == 2
    assert metrics.top_endpoints[0][0] == "/a"

    ip_metrics = monitor.get_ip_metrics("1.1.1.1", window_minutes=1)
    assert ip_metrics["total_requests"] == 4
    endpoint_metrics = monitor.get_endpoint_metrics("/a", window_minutes=1)
    assert endpoint_metrics["rate_limited_requests"] >= 1

    # Suspicious IP detection should flag repeated 429s
    suspicious = monitor.get_suspicious_ips(window_minutes=1, min_requests=3)
    assert suspicious and suspicious[0]["client_ip"] == "1.1.1.1"

    # Export events and ensure file is written
    out_file = tmp_path / "export.jsonl"
    monitor.export_events(out_file, window_minutes=1)
    assert out_file.exists()
    content = out_file.read_text().strip().splitlines()
    assert len(content) == 5
    json.loads(content[0])  # parsable

    # Clear old events
    monitor.clear_old_events(hours_to_keep=0)  # forces cleanup
    assert len(monitor._events) == 0


def test_global_monitor_helpers(monkeypatch):
    rlm = _load_module()
    RateLimitMonitor = rlm.RateLimitMonitor
    RateLimitEvent = rlm.RateLimitEvent
    get_monitor = rlm.get_monitor
    record_rate_limit_event = rlm.record_rate_limit_event

    # Reset global monitor
    monkeypatch.setattr(rlm, "_monitor_instance", None, raising=False)
    monitor = get_monitor()
    record_rate_limit_event(
        "3.3.3.3",
        "/c",
        200,
        0.05,
        user_agent="ua",
        limit_type="global",
        limit_value=5,
        remaining=4,
    )
    metrics = monitor.get_metrics(window_minutes=1)
    assert metrics.total_requests >= 1
