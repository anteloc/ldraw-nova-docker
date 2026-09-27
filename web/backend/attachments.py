"""Bounded, inline raster image inputs. Never fetch arbitrary image URLs."""
import base64
import binascii
import re

MAX_IMAGE_BYTES = 5 * 1024 * 1024


def validate_images(images: list[str]) -> list[str]:
    if len(images) > 4:
        raise ValueError("Attach at most four images")
    total = 0
    for url in images:
        if len(url) > MAX_IMAGE_BYTES * 4 // 3 + 100:
            raise ValueError("Each image must be at most 5 MB")
        match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", url)
        if not match:
            raise ValueError("Images must be PNG, JPEG or WebP data URLs")
        try:
            data = base64.b64decode(match[2], validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Invalid image encoding") from None
        valid = {"png": data.startswith(b"\x89PNG\r\n\x1a\n"), "jpeg": data.startswith(b"\xff\xd8\xff"),
                 "webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP"}
        if not valid[match[1]] or len(data) > MAX_IMAGE_BYTES:
            raise ValueError("Invalid image or image exceeds 5 MB")
        total += len(data)
    if total > 12 * 1024 * 1024:
        raise ValueError("Images must total at most 12 MB")
    return images
