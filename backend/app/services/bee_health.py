import mimetypes
import os
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.auth.auth import supabase
from app.ml_model import ModelUnavailableError, predict

BUCKET = os.getenv("SUPABASE_BEE_IMAGE_BUCKET", "bee-images")
MAX_IMAGE_SIZE = 2 * 1024 * 1024
ALLOWED_FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png")}


def _get_owned_hive(hive_id: str, beekeeper_id: str) -> dict[str, Any]:
    response = (
        supabase.table("hives")
        .select("hive_id, beekeeper_id, image_path, bee_status")
        .eq("hive_id", hive_id)
        .eq("beekeeper_id", beekeeper_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Hive not found")
    return response.data[0]


def get_hive_image(hive_id: str, beekeeper_id: str) -> tuple[bytes, str]:
    hive = _get_owned_hive(hive_id, beekeeper_id)
    image_path = hive.get("image_path")
    if not image_path:
        raise HTTPException(status_code=404, detail="No bee image has been uploaded for this hive")

    try:
        image_bytes = supabase.storage.from_(BUCKET).download(image_path)
    except Exception as error:
        raise HTTPException(status_code=502, detail="Bee image could not be retrieved from storage") from error

    content_type = mimetypes.guess_type(Path(image_path).name)[0]
    if content_type not in {"image/jpeg", "image/png"}:
        content_type = "application/octet-stream"
    return image_bytes, content_type


async def upload_hive_image(hive_id: str, beekeeper_id: str, upload: UploadFile) -> dict[str, Any]:
    hive = _get_owned_hive(hive_id, beekeeper_id)
    image_bytes = await upload.read(MAX_IMAGE_SIZE + 1)
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Choose an image to upload")
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="Bee images must be 2 MB or smaller")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = image.format
            image.verify()
    except (UnidentifiedImageError, OSError) as error:
        raise HTTPException(status_code=400, detail="Upload a valid JPG or PNG image") from error

    if image_format not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail="Only JPG and PNG images are supported")

    extension, content_type = ALLOWED_FORMATS[image_format]
    image_path = f"{beekeeper_id}/{hive_id}/{uuid.uuid4().hex}.{extension}"
    try:
        supabase.storage.from_(BUCKET).upload(
            image_path,
            image_bytes,
            {"content-type": content_type},
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail="Bee image upload failed") from error

    try:
        response = (
            supabase.table("hives")
            .update({"image_path": image_path})
            .eq("hive_id", hive_id)
            .eq("beekeeper_id", beekeeper_id)
            .execute()
        )
        if not response.data:
            raise RuntimeError("Hive image path could not be saved")
    except Exception as error:
        try:
            supabase.storage.from_(BUCKET).remove([image_path])
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Bee image path could not be saved") from error

    previous_path = hive.get("image_path")
    if previous_path and previous_path != image_path:
        try:
            supabase.storage.from_(BUCKET).remove([previous_path])
        except Exception:
            pass
    return response.data[0]


def refresh_hive_bee_status(hive_id: str, beekeeper_id: str) -> dict[str, Any]:
    hive = _get_owned_hive(hive_id, beekeeper_id)
    image_path = hive.get("image_path")
    if not image_path:
        return hive

    try:
        image_bytes = supabase.storage.from_(BUCKET).download(image_path)
    except Exception as error:
        raise HTTPException(status_code=502, detail="Bee image could not be retrieved from storage") from error

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            prediction = predict(image.convert("RGB"))
    except ModelUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (UnidentifiedImageError, OSError) as error:
        raise HTTPException(status_code=422, detail="The stored bee image cannot be read") from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="Bee image assessment failed") from error

    normalized_status = str(prediction.get("bee_status", prediction.get("prediction", ""))).strip().lower()
    bee_status = {"healthy": "Healthy", "infected": "Infected"}.get(normalized_status)
    if bee_status is None:
        raise HTTPException(status_code=500, detail="The model returned an unsupported bee status")

    response = (
        supabase.table("hives")
        .update({"bee_status": bee_status})
        .eq("hive_id", hive_id)
        .eq("beekeeper_id", beekeeper_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=502, detail="Bee status could not be saved")
    return response.data[0]