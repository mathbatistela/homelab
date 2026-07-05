"""Launch Camoufox as a Playwright WebSocket server.

Binds to the loopback internal port; entrypoint.sh's socat bridges the published
port to it. headless=True spawns a virtual display (xvfb) on Linux.
"""
import os

from camoufox.server import launch_server

launch_server(
    headless=True,
    geoip=True,
    port=int(os.environ.get("CAMOUFOX_INTERNAL_PORT", "9223")),
    ws_path=os.environ.get("CAMOUFOX_WS_PATH", "camoufox"),
)
