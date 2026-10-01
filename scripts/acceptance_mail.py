"""Local-only SMTP sink for synthetic acceptance tests; never forwards mail.

python scripts/acceptance_mail.py --smtp-port 1025 --http-port 8025
No payloads or credentials are logged or persisted. The control API belongs only
on loopback or an isolated CI network; never include this service in deployment.
"""

import argparse
import json
import logging
import ssl
import threading
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from aiosmtpd.controller import Controller

messages = []
lock = threading.Lock()
mode = "available"


class Sink:
    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        if not address.lower().endswith("@example.test"):
            return "550 Only synthetic example.test recipients are accepted"
        envelope.rcpt_tos.append(address)
        return "250 OK"

    async def handle_DATA(self, server, session, envelope):
        if mode == "temporary":
            return "451 Synthetic transient failure"
        if mode == "permanent":
            return "550 Synthetic delivery failure"
        parsed = BytesParser(policy=policy.default).parsebytes(envelope.content)
        body = parsed.get_body(preferencelist=("plain",))
        with lock:
            messages.append(
                {
                    "recipients": envelope.rcpt_tos,
                    "subject": str(parsed["Subject"]),
                    "text": body.get_content() if body else "",
                }
            )
            del messages[:-500]
        return "250 Accepted by synthetic sink"


class Control(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Even query strings may contain addresses; keep the sink silent.

    def reply(self, value, status=200):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/health":
            return self.reply({"ready": True})
        recipient = parse_qs(url.query).get("recipient", [""])[0]
        if url.path != "/messages" or not recipient.endswith("@example.test"):
            return self.reply({"error": "Synthetic recipient required"}, 400)
        with lock:
            self.reply([row for row in messages if recipient in row["recipients"]])

    def do_POST(self):
        global mode
        value = urlsplit(self.path).path.removeprefix("/mode/")
        if value not in {"available", "temporary", "permanent"}:
            return self.reply({"error": "Unknown mode"}, 400)
        mode = value
        self.reply({"mode": mode})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--smtp-port", type=int, default=1025)
    parser.add_argument("--http-port", type=int, default=8025)
    parser.add_argument("--cert")
    parser.add_argument("--key")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    tls = None
    if args.cert:
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(args.cert, args.key)
    smtp = Controller(
        Sink(),
        hostname=args.host,
        port=args.smtp_port,
        data_size_limit=1048576,
        tls_context=tls,
        require_starttls=bool(tls),
    )
    smtp.start()
    try:
        ThreadingHTTPServer((args.host, args.http_port), Control).serve_forever()
    finally:
        smtp.stop()
