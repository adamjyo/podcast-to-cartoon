"""Turn a headshot into an ink avatar and a mouth sheet. Needs the user's own xAI key."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image

AVATAR_PROMPT = (
    "Redraw this headshot as a hand-drawn ink and watercolor podcast avatar. "
    "Bust from mid-chest up, facing the camera, mouth gently closed. "
    "Keep this exact person's recognizable face, hair, glasses, facial hair, and clothing colors. "
    "Visible pencil line, soft watercolor wash, plain warm cream paper background, "
    "generous margin, no text, no watermark, no border."
)

MOUTH_PROMPT = (
    "Using this person's drawn face as the style reference, output ONLY a precise "
    "3-column by 2-row grid of six mouths, no full faces. Solid flat background exactly #FF00FF. "
    "Top row left to right: closed lip line, small open mouth, medium talking mouth. "
    "Bottom row: wide open mouth, round O mouth, teeth-on-lip. "
    "Same ink line as the reference, each mouth centered in its cell, nothing crossing cell edges, no labels, no text."
)

MOUTH_NAMES = ("closed", "small", "medium", "wide", "round", "teeth")


def _edit(image_bytes: bytes, prompt: str, api_key: str) -> bytes:
    if not api_key.strip():
        raise RuntimeError("Paste an xAI API key to draw avatars.")
    data_url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()
    body = json.dumps(
        {
            "model": "grok-imagine-image",
            "prompt": prompt,
            "image": {"url": data_url, "type": "image_url"},
            "response_format": "b64_json",
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.x.ai/v1/images/edits",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key.strip()}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            payload = json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"Drawing failed ({exc.code}). {detail}") from exc
    item = (payload.get("data") or [{}])[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        with urllib.request.urlopen(item["url"], timeout=60) as res:
            return res.read()
    raise RuntimeError("No drawing came back. Try again.")


def draw_avatar(photo_path: str, api_key: str, note: str = "") -> bytes:
    extra = f" Extra direction: {note.strip()}" if note.strip() else ""
    photo = Path(photo_path).read_bytes()
    return _edit(photo, AVATAR_PROMPT + extra, api_key)


def draw_mouths(avatar_path: str, api_key: str) -> dict:
    sheet = _edit(Path(avatar_path).read_bytes(), MOUTH_PROMPT, api_key)
    return split_mouth_sheet(sheet)


def split_mouth_sheet(blob: bytes) -> dict:
    image = Image.open(BytesIO(blob)).convert("RGBA")
    w, h = image.size
    cols, rows = 3, 2
    out = {}
    for i, name in enumerate(MOUTH_NAMES):
        c, r = i % cols, i // cols
        x0, x1 = round(c * w / cols), round((c + 1) * w / cols)
        y0, y1 = round(r * h / rows), round((r + 1) * h / rows)
        cell = image.crop((x0, y0, x1, y1))
        px = cell.load()
        cw, ch = cell.size
        for y in range(ch):
            for x in range(cw):
                red, green, blue, _alpha = px[x, y]
                if red > 170 and blue > 150 and green < 140 and red - green > 40 and blue - green > 30:
                    px[x, y] = (0, 0, 0, 0)
        buf = BytesIO()
        cell.save(buf, format="PNG")
        out[name] = buf.getvalue()
    return out
