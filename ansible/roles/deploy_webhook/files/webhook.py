#!/usr/bin/env python3
"""
Generic multi-app deploy webhook receiver — HMAC-secured, Prometheus metrics.

Config file: /opt/deploy/config.yml

  apps:
    <name>:
      compose_dir: /opt/deploy/<name>
      ghcr_user: mathbatistela          # optional
      ghcr_token_file: /opt/deploy/.ghcr_token  # optional, shared default
  webhook:
    port: 9999
    secret: "<shared-hmac-secret>"

Endpoints:
  POST /webhook/<app>     — trigger deploy (HMAC-signed)
  GET  /health            — liveness probe
  GET  /metrics           — Prometheus text metrics
"""
import hashlib
import hmac
import http.server
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import yaml

CONFIG_PATH = os.environ.get("DEPLOY_CONFIG", "/opt/deploy/config.yml")
METRICS = {
    "deploys_total": {},
    "deploy_errors_total": {},
    "last_deploy_ts": {},
    "last_deploy_status": {},
}
server_start_ts = time.time()


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


class DeployHandler(http.server.BaseHTTPRequestHandler):
    config: dict = {}
    secret: str = ""

    def _verify_hmac(self, body: bytes) -> bool:
        sig = self.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(
            self.secret.encode(), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(sig, expected)

    def _deploy(self, app_name: str) -> tuple[int, str]:
        app = self.config.get("apps", {}).get(app_name)
        if not app:
            return 404, f"unknown app: {app_name}"

        compose_dir = app["compose_dir"]
        ghcr_token_file = app.get("ghcr_token_file", "/opt/deploy/.ghcr_token")
        ghcr_user = app.get("ghcr_user", "mathbatistela")

        env = os.environ.copy()
        env["COMPOSE_DIR"] = compose_dir

        script = [
            "#!/bin/bash",
            "set -e",
            f'cd "{compose_dir}"',
        ]
        token_path = Path(ghcr_token_file)
        if token_path.exists():
            script.append(
                f'docker login ghcr.io -u {ghcr_user} --password-stdin < "{ghcr_token_file}" > /dev/null 2>&1'
            )
        script += [
            "docker compose pull",
            "docker compose up -d --force-recreate",
        ]

        try:
            result = subprocess.run(
                ["bash", "-c", "\n".join(script)],
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            ok = result.returncode == 0
            output = result.stdout[-500:] or result.stderr[-500:] or ("ok" if ok else "failed")
            status = 200 if ok else 500
        except subprocess.TimeoutExpired:
            status, output = 504, "deploy timed out"
        except Exception as e:
            status, output = 500, str(e)

        # Update metrics
        METRICS["deploys_total"].setdefault(app_name, 0)
        METRICS["deploys_total"][app_name] += 1
        if status >= 400:
            METRICS["deploy_errors_total"].setdefault(app_name, 0)
            METRICS["deploy_errors_total"][app_name] += 1
        METRICS["last_deploy_ts"][app_name] = time.time()
        METRICS["last_deploy_status"][app_name] = status

        return status, output.strip()

    def do_POST(self):
        # Route: /webhook/<app>
        if not self.path.startswith("/webhook/"):
            self.send_error(404)
            return

        app_name = self.path[len("/webhook/"):].strip("/")
        if not app_name:
            self.send_error(400, "missing app name")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        if not self._verify_hmac(body):
            self.send_error(403, "invalid signature")
            METRICS.setdefault("unauthorized_total", 0)
            METRICS["unauthorized_total"] += 1
            return

        status, msg = self._deploy(app_name)
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(msg.encode())

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")

        elif self.path == "/metrics":
            lines = [
                "# HELP deploy_webhook_uptime_seconds Time since server start",
                "# TYPE deploy_webhook_uptime_seconds gauge",
                f"deploy_webhook_uptime_seconds {time.time() - server_start_ts:.0f}",
                "# HELP deploy_webhook_deploys_total Total deploys per app",
                "# TYPE deploy_webhook_deploys_total counter",
            ]
            for app, count in METRICS.get("deploys_total", {}).items():
                lines.append(f'deploy_webhook_deploys_total{{app="{app}"}} {count}')
            lines += [
                "# HELP deploy_webhook_deploy_errors_total Total deploy errors per app",
                "# TYPE deploy_webhook_deploy_errors_total counter",
            ]
            for app, count in METRICS.get("deploy_errors_total", {}).items():
                lines.append(f'deploy_webhook_deploy_errors_total{{app="{app}"}} {count}')
            lines += [
                "# HELP deploy_webhook_last_deploy_timestamp Last deploy timestamp per app",
                "# TYPE deploy_webhook_last_deploy_timestamp gauge",
            ]
            for app, ts in METRICS.get("last_deploy_ts", {}).items():
                lines.append(f'deploy_webhook_last_deploy_timestamp{{app="{app}"}} {ts:.0f}')
            lines += [
                "# HELP deploy_webhook_unauthorized_total Failed HMAC attempts",
                "# TYPE deploy_webhook_unauthorized_total counter",
                f"deploy_webhook_unauthorized_total {METRICS.get('unauthorized_total', 0)}",
            ]

            body = "\n".join(lines) + "\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode())

        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)


def main():
    cfg = load_config()
    webhook_cfg = cfg.get("webhook", {})
    port = int(webhook_cfg.get("port", 9999))
    secret = webhook_cfg.get("secret", "")

    if not secret:
        print("FATAL: webhook.secret is required in config", file=sys.stderr)
        sys.exit(1)

    DeployHandler.config = cfg
    DeployHandler.secret = secret

    print(f"Deploy webhook on :{port}, {len(cfg.get('apps', {}))} apps (HMAC secured, /metrics enabled)", flush=True)
    http.server.HTTPServer(("0.0.0.0", port), DeployHandler).serve_forever()


if __name__ == "__main__":
    main()
