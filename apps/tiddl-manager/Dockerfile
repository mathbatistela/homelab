# Build on top of tiddl (has Python, ffmpeg, and tiddl CLI)
FROM tiddl:3.4.4

# Install tiddl-manager
COPY pyproject.toml /tmp/tiddl-manager/
COPY src/ /tmp/tiddl-manager/src/

RUN cd /tmp/tiddl-manager && \
    pip install --no-cache-dir . && \
    rm -rf /tmp/tiddl-manager

# Volumes
# - /root/.tiddl: tiddl auth config (shared with tiddl)
# - /root/.tiddl-manager: tiddl-manager state DB
# - /downloads: music download target

VOLUME ["/root/.tiddl", "/root/.tiddl-manager", "/downloads"]

ENTRYPOINT ["tiddl-manager"]
CMD ["--help"]
