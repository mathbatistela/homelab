#!/usr/bin/env python3
"""
Auto-launch reverse proxy for CloakBrowser-Manager CDP.

Listens on localhost:9222. On each request:
1. Checks if the CloakBrowser profile is running
2. Auto-launches if stopped (waits up to 30s)
3. Proxies the request to the real CDP endpoint

Hermes config: browser.cdp_url = http://localhost:9222
"""

import asyncio
import ssl
import time
import sys
import os
from aiohttp import web, ClientSession, ClientWebSocketResponse, WSMsgType, TCPConnector

CLOAKBROWSER_API = os.getenv("CLOAKBROWSER_API", "https://cloakbrowser.local.batistela.tech/api")
PROFILE_ID = os.getenv("CLOAKBROWSER_PROFILE_ID", "2d544629-a40f-404f-a957-0d252b19a1df")
CDP_BACKEND = f"https://cloakbrowser.local.batistela.tech/api/profiles/{PROFILE_ID}/cdp"
LISTEN_HOST = os.getenv("PROXY_LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.getenv("PROXY_LISTEN_PORT", "9222"))
STATUS_TTL = int(os.getenv("PROXY_STATUS_TTL", "10"))  # cache seconds
LAUNCH_TIMEOUT = int(os.getenv("PROXY_LAUNCH_TIMEOUT", "30"))  # max wait for launch

_last_check = 0
_last_ready = False
_lock = asyncio.Lock()


async def ensure_running(session):
    """Check profile status; launch if stopped. Cache result for STATUS_TTL seconds."""
    global _last_check, _last_ready
    async with _lock:
        now = time.time()
        if (now - _last_check) < STATUS_TTL:
            return _last_ready

        # Check status
        async with session.get(f"{CLOAKBROWSER_API}/profiles") as resp:
            profiles = await resp.json()
        profile = next((p for p in profiles if p["id"] == PROFILE_ID), None)

        if profile is None:
            print(f"[proxy] Profile {PROFILE_ID} not found in {CLOAKBROWSER_API}", file=sys.stderr)
            _last_check = now
            _last_ready = False
            return False

        if profile["status"] == "running":
            _last_check = now
            _last_ready = True
            return True

        # Launch
        print(f"[proxy] Profile is '{profile['status']}', launching...", file=sys.stderr)
        async with session.post(f"{CLOAKBROWSER_API}/profiles/{PROFILE_ID}/launch") as resp:
            launch_result = await resp.json()
            print(f"[proxy] Launch response: {launch_result.get('status', 'unknown')}", file=sys.stderr)

        # Wait for running
        for i in range(LAUNCH_TIMEOUT):
            await asyncio.sleep(1)
            async with session.get(f"{CLOAKBROWSER_API}/profiles") as resp:
                profiles = await resp.json()
            p = next((x for x in profiles if x["id"] == PROFILE_ID), None)
            if p and p["status"] == "running":
                print(f"[proxy] ✅ Profile ready (took {i + 1}s)", file=sys.stderr)
                _last_check = time.time()
                _last_ready = True
                return True

        print(f"[proxy] ❌ Launch timeout after {LAUNCH_TIMEOUT}s", file=sys.stderr)
        _last_check = time.time()
        _last_ready = False
        return False


async def proxy_handler(request):
    """Handle all requests: check/launch profile, then reverse-proxy to CDP."""
    session = request.app["client_session"]

    # Ensure profile is running
    ready = await ensure_running(session)
    if not ready:
        return web.Response(status=503, text="CloakBrowser profile not available after auto-launch")

    # Build target URL
    target_url = f"{CDP_BACKEND}{request.path_qs}"

    # Check for WebSocket upgrade
    if request.headers.get("upgrade", "").lower() == "websocket":
        return await proxy_websocket(request, target_url)

    # Regular HTTP proxy
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "transfer-encoding")}
    headers["Host"] = "cloakbrowser.local.batistela.tech"

    body = await request.read()

    try:
        async with session.request(
            request.method, target_url,
            headers=headers,
            data=body,
            allow_redirects=False,
        ) as resp:
            response_body = await resp.read()
            proxy_resp = web.Response(
                status=resp.status,
                body=response_body,
            )
            for k, v in resp.headers.items():
                if k.lower() not in ("transfer-encoding",):
                    proxy_resp.headers[k] = v
            return proxy_resp
    except Exception as e:
        # Invalidate cache on connection error — profile might have died
        global _last_check
        _last_check = 0
        print(f"[proxy] Backend error: {e}", file=sys.stderr)
        return web.Response(status=502, text=f"CDP backend unreachable: {e}")


async def proxy_websocket(request, target_url):
    """Proxy WebSocket connection bidirectionally."""
    session = request.app["client_session"]
    ws_client = web.WebSocketResponse()
    await ws_client.prepare(request)

    target_ws_url = target_url.replace("https://", "wss://")

    try:
        async with session.ws_connect(target_ws_url) as ws_backend:

            async def client_to_backend():
                async for msg in ws_client:
                    if msg.type == WSMsgType.TEXT:
                        await ws_backend.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await ws_backend.send_bytes(msg.data)
                    elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                        break

            async def backend_to_client():
                async for msg in ws_backend:
                    if msg.type == WSMsgType.TEXT:
                        await ws_client.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await ws_client.send_bytes(msg.data)
                    elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                        break

            await asyncio.gather(client_to_backend(), backend_to_client())
    except Exception as e:
        print(f"[proxy] WebSocket error: {e}", file=sys.stderr)

    return ws_client


async def on_startup(app):
    ssl_ctx = ssl.create_default_context()
    conn = TCPConnector(ssl=ssl_ctx, limit=10)
    app["client_session"] = ClientSession(connector=conn)
    print(f"[proxy] Listening on {LISTEN_HOST}:{LISTEN_PORT} → {CDP_BACKEND}", file=sys.stderr)


async def on_cleanup(app):
    await app["client_session"].close()


def main():
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", proxy_handler)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    web.run_app(app, host=LISTEN_HOST, port=LISTEN_PORT, print=None)


if __name__ == "__main__":
    main()
