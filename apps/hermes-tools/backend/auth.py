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
