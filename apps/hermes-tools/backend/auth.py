"""Auth dependencies: Telegram initData validation (Mini App) and MCP API key."""
import hashlib
import hmac
import json
import logging
import time
from urllib.parse import unquote_plus

from fastapi import HTTPException, Request

from config import get_settings

logger = logging.getLogger("auth")


def _compute_hash(data_check_string: str, bot_token: str) -> str:
    """HMAC-SHA256 per Telegram spec: secret = HMAC(bot_token, key='WebAppData')."""
    secret_key = hmac.new(
        key="WebAppData".encode(),
        msg=bot_token.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    return hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()


def validate_init_data(init_data: str) -> dict:
    """Validate Telegram initData against TELEGRAM_BOT_TOKEN using the decoded key=value pairs."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN não configurado")

    # The data-check-string must use URL-DECODED values per Telegram's spec —
    # the client computes the hash over decoded key=value pairs, not the
    # percent-encoded query string. unquote_plus (not unquote) because
    # Telegram encodes spaces as '+'.
    pairs_raw = []
    user_raw = None
    auth_date_raw = None
    received_hash = None

    for pair in init_data.split("&"):
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        decoded_value = unquote_plus(value)
        if key == "hash":
            received_hash = decoded_value
        elif key == "user":
            user_raw = json.loads(decoded_value)
        elif key == "auth_date":
            auth_date_raw = int(decoded_value)
        if key != "hash":
            pairs_raw.append((key, decoded_value))

    if received_hash is None:
        raise HTTPException(status_code=401, detail="Hash ausente no initData")

    # Sort by key, exclude only "hash" — "signature" (Ed25519, Bot API 7.2+) is
    # a real data field and IS part of the HMAC data-check-string.
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs_raw) if k != "hash")
    expected_hash = _compute_hash(data_check_string, settings.telegram_bot_token)

    if not hmac.compare_digest(received_hash, expected_hash):
        logger.warning(
            "Hash mismatch. enforce=%s data_check_string=%r",
            settings.telegram_auth_enforce, data_check_string,
        )
        if settings.telegram_auth_enforce:
            raise HTTPException(status_code=401, detail="Hash inválido")
        # Fail-open path: TELEGRAM_AUTH_ENFORCE=false accepts initData whose
        # HMAC does not match, so the caller-supplied user_id (and therefore
        # ALLOWED_USER_IDS) is forgeable. Never silently — shout on every
        # request that takes this branch.
        logger.error(
            "SECURITY: accepting UNVERIFIED Telegram initData because "
            "TELEGRAM_AUTH_ENFORCE=false. The user id in this request is "
            "forgeable and ALLOWED_USER_IDS provides no protection. "
            "Set TELEGRAM_AUTH_ENFORCE=true."
        )

    if auth_date_raw and abs(time.time() - auth_date_raw) > 86400:
        raise HTTPException(status_code=401, detail="initData expirado")

    result = {}
    if user_raw:
        result["user"] = user_raw
    return result


async def require_telegram_user(request: Request) -> dict:
    init_data = (
        request.headers.get("X-Telegram-Init-Data")
        or request.headers.get("tg-init-data")
    )
    if not init_data and request.method == "POST":
        try:
            body = await request.json()
            init_data = body.get("init_data", "")
        except Exception:
            pass
    if not init_data:
        raise HTTPException(status_code=401, detail="initData não informado")

    data = validate_init_data(init_data)
    user = data.get("user", {})
    user_id = user.get("id")

    settings = get_settings()
    allowed = settings.allowed_user_id_set
    if allowed and user_id not in allowed:
        raise HTTPException(status_code=403, detail="Usuário não autorizado")

    return data


def check_mcp_api_key(provided: str) -> bool:
    settings = get_settings()
    if not settings.mcp_api_key:
        return False
    return hmac.compare_digest(provided or "", settings.mcp_api_key)


def extract_api_key(request: Request) -> str:
    """Read the MCP API key from X-API-Key or an Authorization: Bearer header."""
    provided = request.headers.get("x-api-key", "")
    if not provided:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            provided = auth_header[7:]
    return provided


async def require_api_key_or_telegram_user(request: Request) -> dict:
    """Auth for endpoints reachable by both the bot and the Mini App.

    Accepts either of the two credentials this backend already uses:
      * the MCP API key (X-API-Key / Authorization: Bearer) — how the bot calls in
      * Telegram initData (X-Telegram-Init-Data header) — how the Mini App calls in
    """
    provided = extract_api_key(request)
    if provided and check_mcp_api_key(provided):
        return {"auth": "api_key"}

    init_data = (
        request.headers.get("X-Telegram-Init-Data")
        or request.headers.get("tg-init-data")
    )
    if not init_data:
        raise HTTPException(
            status_code=401,
            detail="Credencial ausente (X-API-Key ou X-Telegram-Init-Data)",
        )

    data = validate_init_data(init_data)
    user_id = data.get("user", {}).get("id")

    settings = get_settings()
    allowed = settings.allowed_user_id_set
    if allowed and user_id not in allowed:
        raise HTTPException(status_code=403, detail="Usuário não autorizado")

    return data


def warn_if_auth_misconfigured() -> None:
    """Emit a startup warning for fail-open / missing-credential configurations."""
    settings = get_settings()
    if not settings.telegram_auth_enforce:
        logger.error(
            "SECURITY: TELEGRAM_AUTH_ENFORCE=false — Telegram initData hashes are "
            "checked but NOT enforced. Forged initData (including an arbitrary "
            "user_id) will be accepted. Only use this for local development."
        )
    if not settings.mcp_api_key:
        logger.warning(
            "MCP_API_KEY is empty — /mcp and API-key auth will reject every request."
        )
