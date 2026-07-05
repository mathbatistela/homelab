# Camoufox stealth-browser Playwright WebSocket server.
# Runs Camoufox (stealth Firefox) headless under a virtual display and exposes a
# Playwright-compatible WS endpoint. socat bridges the published port to the
# loopback port Camoufox binds, so external clients can always reach it.
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

# Runtime libs for Firefox + xvfb (virtual display) + socat/netcat for bridging.
RUN apt-get update && apt-get install -y --no-install-recommends \
      xvfb socat netcat-openbsd ca-certificates fonts-liberation \
      libgtk-3-0 libx11-xcb1 libx11-6 libxcb1 libxext6 libxi6 \
      libasound2 libdbus-glib-1-2 libxtst6 libxrandr2 libxcomposite1 \
      libxdamage1 libxfixes3 libxcursor1 libgbm1 libpango-1.0-0 \
      libcairo2 libatk1.0-0 libatk-bridge2.0-0 libnss3 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Camoufox + geoip (recommended for realistic geolocation).
RUN pip install --no-cache-dir "camoufox[geoip]"

# Download the Camoufox browser build (and geoip data) into the image.
RUN python -m camoufox fetch

# camoufox 0.4.11 (latest on PyPI) does NOT pin Playwright, so pip pulls the
# newest (>=1.61) whose driver dropped lib/browserServerImpl.js — the exact file
# camoufox's launchServer.js requires (crash: MODULE_NOT_FOUND). Playwright 1.51+
# also broke camoufox (daijro/camoufox#230). Pin the last compatible release.
# Done as a separate step (after fetch) to keep the browser-download layer cached.
RUN pip install --no-cache-dir "playwright==1.50.0"

COPY server.py entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh
WORKDIR /app

ENV CAMOUFOX_PORT=9222 \
    CAMOUFOX_INTERNAL_PORT=9223 \
    CAMOUFOX_WS_PATH=camoufox

EXPOSE 9222
ENTRYPOINT ["/app/entrypoint.sh"]
