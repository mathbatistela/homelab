FROM node:22-alpine

# mcp-evolution is a stdio MCP server. supergateway bridges it to streamable
# HTTP so it can run as a long-lived container behind Traefik.
ARG MCP_EVOLUTION_REPO=https://github.com/billyfranklim1/mcp-evolution.git
ARG MCP_EVOLUTION_COMMIT=27eb16da797cbee5fed12c4278be1daaed087f05

RUN apk add --no-cache git && \
    git clone "${MCP_EVOLUTION_REPO}" /opt/mcp-evolution && \
    cd /opt/mcp-evolution && \
    git checkout "${MCP_EVOLUTION_COMMIT}" && \
    npm ci && \
    npm run build && \
    npm prune --omit=dev && \
    chmod +x /opt/mcp-evolution/dist/index.js && \
    ln -s /opt/mcp-evolution/dist/index.js /usr/local/bin/mcp-evolution && \
    npm install -g supergateway && \
    rm -rf /root/.npm /opt/mcp-evolution/.git

ENV NODE_ENV=production
EXPOSE 3020

ENTRYPOINT ["supergateway"]
