"""Hermes Tools — extensible AI tools platform: REST API, MCP server, Telegram Mini App."""
import contextlib
import logging
import os
import uuid
from pathlib import Path
from urllib.parse import quote

import aiofiles
import httpx
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import mcp_server
from auth import (
    require_api_key_or_telegram_user,
    require_telegram_user,
    warn_if_auth_misconfigured,
)
from config import get_settings
from tools import get_tool, list_sets, list_tools
from tools.design.remove_bg_rmbg import remove_background as rmbg_remove_background

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hermes-tools")

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"

settings = get_settings()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    warn_if_auth_misconfigured()
    async with mcp_server.mcp.session_manager.run():
        yield


app = FastAPI(title="Hermes Tools", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Public endpoints ---

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "hermes-tools", "tools": len(list_tools())}


@app.get("/api/tool-sets")
async def tool_sets():
    return {"sets": list_sets()}


@app.get("/api/tools")
async def tools_list(set: str | None = None):
    return {"tools": list_tools(set_name=set)}


class PrepareRequest(BaseModel):
    file_id: str


@app.post("/api/prepare")
async def prepare_image(req: PrepareRequest):
    """Download an image from Telegram and return a persistent URL for the Mini App."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN não configurado")

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/getFile",
            params={"file_id": req.file_id},
        )
        data = r.json()
        if not data.get("ok"):
            raise HTTPException(status_code=400, detail=f"Telegram getFile falhou: {data}")

        file_path = data["result"]["file_path"]
        tg_url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"

        resp = await client.get(tg_url)
        resp.raise_for_status()

    job_id = uuid.uuid4().hex[:12]
    ext = file_path.rsplit(".", 1)[-1] if "." in file_path else "jpg"
    local_path = settings.upload_dir / f"{job_id}.{ext}"
    async with aiofiles.open(local_path, "wb") as f:
        await f.write(resp.content)

    image_url = f"{settings.mini_app_url.rstrip('/')}/api/download/{local_path.name}"
    mini_app_url = (
        f"{settings.mini_app_url}?tool=remove-bg-rmbg&platform=telegram"
        f"&image_url={quote(image_url, safe='')}"
    )

    return {"mini_app_url": mini_app_url, "image_url": image_url}


# --- Authenticated endpoints (Telegram initData) ---

class ProcessRequest(BaseModel):
    init_data: str = ""
    params: dict = {}


@app.post("/api/{tool_name}/process")
async def process_tool(
    tool_name: str,
    req: ProcessRequest,
    _auth: dict = Depends(require_telegram_user),
):
    """Generic process endpoint — routes to the correct tool via the registry."""
    tool = get_tool(tool_name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Ferramenta '{tool_name}' não encontrada")

    result = await tool.process(req.params or {})
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return JSONResponse({"ok": True, "data": result.data})


@app.post("/api/remove-bg/upload")
async def remove_bg_upload(
    file: UploadFile = File(...),
    _auth: dict = Depends(require_api_key_or_telegram_user),
):
    """Upload an image file, get an RGBA PNG back.

    Runs GPU/CPU-heavy inference, so it requires a credential: the MCP API key
    (X-API-Key / Bearer — how the bot calls in) or Telegram initData in the
    X-Telegram-Init-Data header (how the Mini App calls in).
    """
    job_id = uuid.uuid4().hex[:12]
    ext = (file.filename or "img.jpg").rsplit(".", 1)[-1] or "jpg"
    local_path = settings.upload_dir / f"{job_id}.{ext}"
    try:
        content = await file.read()
        local_path.write_bytes(content)
        result_path = rmbg_remove_background(local_path)
        return FileResponse(
            result_path,
            media_type="image/png",
            filename=f"{Path(file.filename or 'image').stem}_nobg.png",
        )
    finally:
        local_path.unlink(missing_ok=True)


@app.get("/api/download/{filename}")
async def download_result(filename: str):
    safe_name = os.path.basename(filename)
    path = settings.upload_dir / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return FileResponse(path, media_type="image/png")


# --- MCP server ---
app.mount("/mcp", mcp_server.mcp_asgi_app)


# --- Frontend ---
if FRONTEND_DIST_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend")
else:
    logger.warning("frontend/dist não encontrado (%s) — servindo apenas a API", FRONTEND_DIST_DIR)
