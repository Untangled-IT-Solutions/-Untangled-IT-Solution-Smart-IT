"""Startup must construct immediately even when health checks are delayed."""

import threading
import time


def test_three_second_health_check_does_not_delay_application(monkeypatch):
    from app import application as module

    started_health = threading.Event()
    finished_health = threading.Event()

    class Root:
        def winfo_toplevel(self):
            return self

        def winfo_exists(self):
            return True

        def after(self, delay, callback):
            return "unused-test-job"

    class Backend:
        base_url = "http://test.invalid"
        token = None
        session_data = None

        def health(self):
            started_health.set()
            time.sleep(3)
            finished_health.set()
            return {"status": "ok"}

    monkeypatch.setattr(module.Application, "_init_ui", lambda self: setattr(self, "_temp_root", Root()))
    monkeypatch.setattr(module, "BackendAPIClient", Backend)
    started = time.monotonic()
    app = module.Application()
    elapsed = time.monotonic() - started
    assert elapsed < .5
    assert started_health.wait(1)
    assert not finished_health.is_set()
    assert finished_health.wait(4)
    assert app.backend.base_url == "http://test.invalid"
