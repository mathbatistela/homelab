import http.server
import json
import os
import socketserver

PORT = int(os.environ.get("PORT", 8080))


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        elif self.path == "/":
            self._respond(200, {"message": "Hello from the homelab!", "app": "hello-world"})
        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}", flush=True)


with socketserver.TCPServer(("", PORT), Handler) as server:
    print(f"Listening on :{PORT}", flush=True)
    server.serve_forever()
