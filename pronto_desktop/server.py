"""Bounded, loopback-only WSGI hosting for one local desktop user.

This stdlib server is a local workstation convenience, not a deployment server.
Report authentication and CSRF protection continue to be handled by Django.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
from socketserver import ThreadingMixIn
import threading
from urllib.parse import parse_qs
from urllib.request import ProxyHandler, Request, build_opener
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from . import __version__

HEALTH_PATH = "/__pronto_health__/"


class _LocalRequestHandler(WSGIRequestHandler):
    def handle(self):
        self.request.settimeout(20)
        super().handle()

    def log_message(self, format, *args):
        # URLs can contain sample identifiers. Do not echo them into desktop logs.
        pass


class _ThreadedServer(ThreadingMixIn, WSGIServer):
    # Closing the desktop must let report saves and PDF exports finish.
    daemon_threads = False
    block_on_close = True
    allow_reuse_address = False

    def __init__(self, *args, **kwargs):
        self._slots = threading.BoundedSemaphore(16)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


class LocalServer:
    """Own one server, or reuse a server proving the same private DB identity."""

    def __init__(self, application, *, secret: str, database: Path, port: int = 8770):
        if isinstance(port, bool) or not isinstance(port, int) or (port != 0 and not 1024 <= port <= 65535):
            raise ValueError("Port must be between 1024 and 65535 (0 selects a free test port).")
        self.application = application
        self.port = port
        canonical = str(Path(database).resolve())
        if os.name == "nt":
            canonical = canonical.casefold()
        self._key = hmac.digest(secret.encode(), b"PRONTO-local-db-v1:" + canonical.encode(), "sha256")
        self._identity = hashlib.sha256(self._key).hexdigest()
        self._httpd = None
        self._thread = None
        self._reused = False
        self._reuse_running = False
        self._monitor_stop = threading.Event()
        self._monitor_thread = None
        self._lock = threading.RLock()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/reports/"

    @property
    def owned(self) -> bool:
        return self._httpd is not None and self._thread is not None and self._thread.is_alive()

    @property
    def running(self) -> bool:
        # GUI status reads must never perform network I/O. A compatible reused
        # server is checked by a separate monitor; start() always proves it again.
        return self.owned or (self._reused and self._reuse_running)

    def _monitor_existing(self, stopped: threading.Event) -> None:
        while not stopped.wait(2):
            healthy = self._matches_existing()
            if stopped.is_set():
                break
            self._reuse_running = healthy

    def _stop_monitor(self) -> None:
        self._monitor_stop.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=2)
            self._monitor_thread = None
        self._reuse_running = False

    def _matches_existing(self) -> bool:
        challenge = secrets.token_hex(24)
        request = Request(f"http://127.0.0.1:{self.port}{HEALTH_PATH}?challenge={challenge}")
        try:
            # Loopback never goes through system or corporate HTTP proxies.
            with build_opener(ProxyHandler({})).open(request, timeout=1) as response:
                payload = json.loads(response.read(4097))
            expected = hmac.digest(self._key, challenge.encode(), "sha256").hex()
            return (payload.get("app") == "PRONTO" and payload.get("version") == __version__
                    and payload.get("identity") == self._identity
                    and hmac.compare_digest(str(payload.get("proof", "")), expected))
        except (OSError, ValueError, TypeError, AttributeError):
            return False

    def _application(self, environ, start_response):
        host = environ.get("HTTP_HOST", "").split(":", 1)[0].lower()
        if host not in {"127.0.0.1", "localhost"}:
            start_response("400 Bad Request", [("Content-Type", "text/plain")])
            return [b"Invalid local host"]
        if environ.get("PATH_INFO") == HEALTH_PATH:
            challenge = parse_qs(environ.get("QUERY_STRING", "")).get("challenge", [""])[0]
            if environ.get("REQUEST_METHOD") != "GET" or not 1 <= len(challenge) <= 128:
                start_response("400 Bad Request", [("Content-Type", "text/plain")])
                return [b"A bounded challenge is required"]
            payload = json.dumps({"app": "PRONTO", "version": __version__, "identity": self._identity,
                                  "proof": hmac.digest(self._key, challenge.encode(), "sha256").hex()}).encode()
            start_response("200 OK", [("Content-Type", "application/json"),
                                       ("Content-Length", str(len(payload))), ("Cache-Control", "no-store")])
            return [payload]
        return self.application(environ, start_response)

    def start(self) -> str:
        with self._lock:
            if self.owned:
                return self.url
            if self._reused and self._matches_existing():
                self._reuse_running = True
                return self.url
            self._stop_monitor()
            self._reused = False
            try:
                httpd = make_server("127.0.0.1", self.port, self._application,
                                    server_class=_ThreadedServer, handler_class=_LocalRequestHandler)
            except OSError as error:
                if self.port and self._matches_existing():
                    self._reused = True
                    self._reuse_running = True
                    self._monitor_stop = threading.Event()
                    self._monitor_thread = threading.Thread(target=self._monitor_existing,
                                                            args=(self._monitor_stop,),
                                                            name="PRONTO-server-status", daemon=True)
                    self._monitor_thread.start()
                    return self.url
                raise RuntimeError(f"Port {self.port} is occupied by another service or PRONTO database. "
                                   "Choose another port; the existing service was left running.") from error
            self.port = httpd.server_port
            self._httpd = httpd
            self._reused = False
            self._thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.1},
                                            name="PRONTO-local-server", daemon=True)
            self._thread.start()
            return self.url

    def stop(self) -> None:
        with self._lock:
            # A reused server belongs to the application which originally started it.
            self._stop_monitor()
            self._reused = False
            if self._httpd is not None:
                self._httpd.shutdown()
                self._httpd.server_close()
                if self._thread:
                    self._thread.join(timeout=5)
                self._httpd = None
                self._thread = None
