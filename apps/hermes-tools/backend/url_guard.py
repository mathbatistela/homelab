"""SSRF guard for caller-supplied URLs.

Tools take an `image_url` straight from the caller (REST `/api/{tool}/process`
and the MCP tools both do), and the container sits on the homelab LAN — an
unchecked fetch is a request forgery primitive against every other host on
192.168.1.0/24. Everything that fetches a caller-supplied URL must go through
`fetch_allowed_url()`.

Two layers:
  1. Host allowlist — Telegram (where images actually come from) plus this
     app's own MINI_APP_URL host, since `/api/prepare` mints image URLs
     pointing back at `/api/download/...`. Extendable via IMAGE_URL_EXTRA_HOSTS.
  2. Resolved-address check — anything that resolves into RFC1918, loopback,
     link-local, or other non-global space is refused. Skipped only for hosts
     the operator configured explicitly (MINI_APP_URL / IMAGE_URL_EXTRA_HOSTS),
     which are legitimately internal in a homelab.

Redirects are followed manually so every hop is validated; letting httpx follow
them would let an allowlisted host bounce the fetch anywhere.
"""
import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

from config import get_settings

logger = logging.getLogger("url_guard")

ALLOWED_SCHEMES = {"http", "https"}

# Telegram's API host plus the domains it serves files from.
TELEGRAM_HOSTS = frozenset({"telegram.org", "telegram.me", "telesco.pe", "t.me"})
TELEGRAM_HOST_SUFFIXES = (".telegram.org", ".telegram.me", ".telesco.pe", ".t.me")

MAX_REDIRECTS = 5


class UrlNotAllowed(ValueError):
    """Raised when a caller-supplied URL fails validation."""


def _configured_hosts() -> tuple[set[str], tuple[str, ...]]:
    """Hosts trusted by explicit configuration: (exact names, dotted suffixes)."""
    settings = get_settings()
    exact: set[str] = set()
    suffixes: list[str] = []

    own_host = urlparse(settings.mini_app_url).hostname
    if own_host:
        exact.add(own_host.lower())

    for entry in settings.image_url_extra_hosts_list:
        if entry.startswith("."):
            suffixes.append(entry)
        else:
            exact.add(entry)

    return exact, tuple(suffixes)


def _matches(host: str, exact: set[str], suffixes: tuple[str, ...]) -> bool:
    return host in exact or any(host.endswith(suffix) for suffix in suffixes)


def _is_configured_host(host: str) -> bool:
    exact, suffixes = _configured_hosts()
    return _matches(host, exact, suffixes)


def _is_telegram_host(host: str) -> bool:
    return _matches(host, set(TELEGRAM_HOSTS), TELEGRAM_HOST_SUFFIXES)


def _assert_globally_routable(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UrlNotAllowed(f"host '{host}' não pôde ser resolvido: {exc}") from exc

    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
        ):
            raise UrlNotAllowed(
                f"host '{host}' resolve para um endereço interno ({addr}) — bloqueado"
            )


def validate_url(url: str) -> str:
    """Validate a caller-supplied URL. Returns it, or raises UrlNotAllowed."""
    parsed = urlparse(url)

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UrlNotAllowed(f"esquema '{parsed.scheme}' não permitido (use http/https)")

    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise UrlNotAllowed("URL sem host")

    configured = _is_configured_host(host)
    if not configured and not _is_telegram_host(host):
        raise UrlNotAllowed(f"host '{host}' não está na allowlist de origens de imagem")

    # Hosts trusted by configuration may legitimately be internal (e.g. a
    # LAN-only MINI_APP_URL); everything else must be publicly routable.
    if not configured:
        _assert_globally_routable(host)

    return url


async def fetch_allowed_url(url: str, *, timeout: float = 30.0) -> httpx.Response:
    """GET an allowlisted URL, re-validating every redirect hop."""
    current = validate_url(url)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            resp = await client.get(current)
            if not resp.is_redirect:
                resp.raise_for_status()
                return resp

            location = resp.headers.get("location")
            if not location:
                raise UrlNotAllowed("redirecionamento sem cabeçalho Location")
            next_url = str(resp.url.join(location))
            logger.info("Redirect %s -> %s (revalidando)", current, next_url)
            current = validate_url(next_url)

    raise UrlNotAllowed(f"excesso de redirecionamentos (>{MAX_REDIRECTS})")
