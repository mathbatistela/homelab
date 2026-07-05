# Custom build of s-stefanov/actual-mcp for Actual Budget 26.5.0.
#
# Upstream sstefanov/actual-mcp:latest (v1.11.3 as of 2026-06-02) ships
# @actual-app/api ^26.3.0, which fails with "out-of-sync-migrations" against
# Actual server 26.5.0. It also shuts down the API after every tool call,
# triggering Actual's /account/login rate limit.
#
# This Dockerfile pins the repo at a commit with @actual-app/api ^26.5.0 and
# applies a patch to keep the singleton connection alive.
#
# Build:
#   docker build -t actual-mcp:custom-26.5.0 -f ansible/roles/mcp_servers/files/actual-mcp/Dockerfile .
#
# The build context must include the patches/ directory.

# ---- Builder ----
FROM node:24-alpine AS builder

WORKDIR /app

RUN apk add --no-cache git

ARG ACTUAL_MCP_REPO=https://github.com/s-stefanov/actual-mcp.git
ARG ACTUAL_MCP_COMMIT=24925803dff2dfb697cb6e53c06662ee66c94f01

RUN git clone "${ACTUAL_MCP_REPO}" . && \
    git checkout "${ACTUAL_MCP_COMMIT}"

COPY patches/ /tmp/patches/
RUN for p in /tmp/patches/*.patch; do [ -f "$p" ] && git apply "$p"; done

RUN npm ci
RUN npm run build

# ---- Release ----
FROM node:24-alpine AS release

WORKDIR /app

COPY --from=builder /app/package.json ./
COPY --from=builder /app/package-lock.json ./
COPY --from=builder /app/build ./build

ENV NODE_ENV=production
RUN npm ci --omit=dev

EXPOSE 3000
ENTRYPOINT ["node", "build/index.js"]
