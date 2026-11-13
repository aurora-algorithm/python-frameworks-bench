"""Counts a server's access-log lines and serves them as requests_total for Prometheus (demo runs only).
usage: requests_exporter.py <access log file> <port>"""

import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

count = 0


def tail(path: str) -> None:
    global count
    with open(path, "rb") as f:
        while True:
            line = f.readline()
            if line.endswith(b"\n"):
                count += b'" ' in line and b"HTTP/" in line
            else:
                time.sleep(0.05)


class Metrics(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = f"# TYPE requests_total counter\nrequests_total {count}\n".encode()
        self.send_response(200)
        self.send_header("content-type", "text/plain; version=0.0.4")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


if __name__ == "__main__":
    threading.Thread(target=tail, args=(sys.argv[1],), daemon=True).start()
    HTTPServer(("127.0.0.1", int(sys.argv[2])), Metrics).serve_forever()
