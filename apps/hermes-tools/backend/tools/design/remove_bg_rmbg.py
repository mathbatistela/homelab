"""RMBG-2.0 (BRIA AI) background removal tool.

briaai/RMBG-2.0 is a gated model on Hugging Face — loading it requires an
authenticated token (HF_TOKEN) with access granted to the gated repo, passed
explicitly to `from_pretrained` rather than relying on ambient auth.
"""
import logging
import uuid
from pathlib import Path

import httpx
import torch
from PIL import Image
from pydantic import BaseModel, Field
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

from config import get_settings
from .base import BaseTool, ToolResult

logger = logging.getLogger("tool.remove_bg_rmbg")

MODEL_ID = "briaai/RMBG-2.0"
IMAGE_SIZE = (1024, 1024)

_transform = transforms.Compose([
    transforms.Resize(IMAGE_SIZE),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

_model = None
_device: torch.device | None = None


def _get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def _load_model() -> None:
    global _model, _device
    if _model is not None:
        return
    settings = get_settings()
    _device = _get_device()
    logger.info("Loading RMBG-2.0 on %s...", _device)
    _model = AutoModelForImageSegmentation.from_pretrained(
        MODEL_ID,
        trust_remote_code=True,
        token=settings.hf_token or None,
    )
    _model.to(_device)
    _model.eval()
    torch.set_float32_matmul_precision("high")
    logger.info("RMBG-2.0 loaded")


def remove_background(image_path: str | Path) -> Path:
    """Remove background from image using RMBG-2.0. Returns path to RGBA PNG."""
    _load_model()
    image = Image.open(image_path).convert("RGB")
    original_size = image.size

    input_tensor = _transform(image).unsqueeze(0).to(_device)
    with torch.no_grad():
        preds = _model(input_tensor)[-1].sigmoid().cpu()
    mask = preds[0].squeeze()
    mask_pil = transforms.ToPILImage()(mask)
    mask_pil = mask_pil.resize(original_size, Image.LANCZOS)

    image.putalpha(mask_pil)
    output_path = Path(image_path).with_suffix(".nobg.png")
    image.save(output_path, "PNG")
    logger.info("Saved: %s", output_path)
    return output_path


class RemoveBgRmbgParams(BaseModel):
    image_url: str = Field(..., description="URL pública da imagem a processar")


class RemoveBgRmbgTool(BaseTool):
    name = "remove-bg-rmbg"
    label = "Remover Fundo (RMBG-2.0)"
    description = "Remove o fundo de fotos automaticamente usando o RMBG-2.0 da BRIA AI"
    params_model = RemoveBgRmbgParams

    async def process(self, params: dict) -> ToolResult:
        settings = get_settings()
        parsed = RemoveBgRmbgParams.model_validate(params)

        job_id = uuid.uuid4().hex[:12]
        local_path = settings.upload_dir / f"{job_id}.jpg"

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(parsed.image_url)
                resp.raise_for_status()
                local_path.write_bytes(resp.content)
        except Exception as e:
            return ToolResult(success=False, error=f"Falha ao baixar imagem: {e}")

        try:
            result_path = remove_background(local_path)
        except Exception as e:
            logger.exception("Erro RMBG-2.0")
            return ToolResult(success=False, error=f"Erro ao processar: {e}")
        finally:
            local_path.unlink(missing_ok=True)

        return ToolResult(success=True, data={"result_filename": result_path.name})
