"""Deterministic, process-local fixtures for external protocol tests."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import StreamRequestHandler, ThreadingTCPServer
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from time import sleep


class _LoopbackServer:
    def __enter__(self):
        self._thread = Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()

    @property
    def port(self) -> int:
        return self._server.server_address[1]


@dataclass(frozen=True)
class HttpResponse:
    status: int = 200
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0


class LocalHttpTestServer(_LoopbackServer):
    def __init__(self, routes: dict[tuple[str, str], HttpResponse]):
        self.requests: list[dict] = []
        self._routes = dict(routes)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 <= size <= 1024 * 1024:
                    self.send_error(413)
                    return
                self.connection.settimeout(2)
                owner.requests.append({
                    "method": self.command, "path": self.path, "headers": dict(self.headers),
                    "body": self.rfile.read(size),
                })
                response = owner._routes.get((self.command, self.path), HttpResponse(status=404))
                sleep(response.delay)
                self.send_response(response.status)
                for header, value in response.headers.items():
                    self.send_header(header, value)
                self.send_header("Content-Length", str(len(response.body)))
                self.end_headers()
                if self.command != "HEAD":
                    try:
                        self.wfile.write(response.body)
                    except (BrokenPipeError, ConnectionResetError):
                        pass

            do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_GET

            def log_message(self, *args):
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


class LocalSmtpCaptureServer(_LoopbackServer):
    def __init__(self):
        self.messages: list[dict] = []
        owner = self

        class Handler(StreamRequestHandler):
            def handle(self):
                self.request.settimeout(15)
                self.wfile.write(b"220 parity.test ESMTP\r\n")
                sender = ""
                recipients = []
                while line := self.rfile.readline(65536):
                    command, _, argument = line.strip().partition(b" ")
                    command = command.upper()
                    if command in {b"EHLO", b"HELO"}:
                        response = b"250 parity.test\r\n"
                    elif command == b"MAIL" and argument.upper().startswith(b"FROM:"):
                        sender = argument[5:].decode("ascii")
                        recipients = []
                        response = b"250 OK\r\n"
                    elif command == b"RCPT" and sender and argument.upper().startswith(b"TO:"):
                        recipients.append(argument[3:].decode("ascii"))
                        response = b"250 OK\r\n"
                    elif command == b"DATA" and recipients:
                        self.wfile.write(b"354 End with <CRLF>.<CRLF>\r\n")
                        data = bytearray()
                        while line := self.rfile.readline(65536):
                            if line == b".\r\n":
                                break
                            data.extend(line[1:] if line.startswith(b"..") else line)
                            if len(data) > 16 * 1024 * 1024:
                                self.wfile.write(b"552 Message too large\r\n")
                                return
                        if not line:
                            return
                        parsed = BytesParser(policy=policy.default).parsebytes(bytes(data))
                        owner.messages.append({
                            "sender": sender, "recipients": tuple(recipients), "mime": bytes(data),
                            "attachments": [
                                {"filename": part.get_filename(), "sha256": hashlib.sha256(part.get_payload(decode=True)).hexdigest()}
                                for part in parsed.iter_attachments()
                            ],
                        })
                        sender, recipients = "", []
                        response = b"250 Accepted\r\n"
                    elif command == b"RSET":
                        sender, recipients = "", []
                        response = b"250 OK\r\n"
                    elif command == b"QUIT":
                        self.wfile.write(b"221 Bye\r\n")
                        return
                    else:
                        response = b"503 Unsupported command or sequence\r\n"
                    self.wfile.write(response)

        self._server = ThreadingTCPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True


class IsolatedCommandSandbox:
    """Use a fresh working directory and a fixed Python entry point."""

    def __enter__(self):
        self._temp = TemporaryDirectory(prefix="alteryx-parity-command-")
        self.directory = Path(self._temp.name)
        self.script = self.directory / "command_fixture.py"
        self.script.write_text(
            "import json, sys\nfrom pathlib import Path\n"
            "arguments = sys.argv[2:]\n"
            "Path('command-output.json').write_text(json.dumps(arguments), encoding='utf-8')\n"
            "print(json.dumps(arguments))\n"
            "raise SystemExit(int(sys.argv[1]))\n",
            encoding="utf-8",
        )
        return self

    def arguments(self, exit_code: int = 0, values: Iterable[str] = ()) -> list[str]:
        return [sys.executable, "-I", str(self.script), str(exit_code), *values]

    def __exit__(self, *exc):
        self._temp.cleanup()
