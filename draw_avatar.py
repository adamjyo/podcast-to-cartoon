"""Turn a headshot into an ink avatar and a mouth sheet. Needs the user's own xAI key."""

from __future__ import annotations

import base64
import json
import ssl
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path

import certifi
from PIL import Image


def _open(req, timeout):
    context = ssl.create_default_context(cafile=certifi.where())
    return urllib.request.urlopen(req, timeout=timeout, context=context)

AVATAR_PROMPT = (
    "Completely redraw this person as a hand-drawn ink and watercolor cartoon. "
    "Do not return the photograph. Do not look photorealistic. "
    "Bust from mid-chest up, facing the camera, mouth gently closed. "
    "Keep the same recognizable face, hair, glasses, facial hair, and clothing colors, "
    "but render them with visible pencil lines and a soft watercolor wash on plain warm cream paper. "
    "No text, no watermark, no border."
)

MOUTH_PROMPT = (
    "Using this person's drawn face as the style reference, output ONLY a precise "
    "3-column by 2-row grid of six mouths, no full faces. Solid flat background exactly #FF00FF. "
    "Top row left to right: closed lip line, small open mouth, medium talking mouth. "
    "Bottom row: wide open mouth, round O mouth, teeth-on-lip. "
    "Same ink line as the reference, each mouth centered in its cell, nothing crossing cell edges, no labels, no text."
)

MOUTH_NAMES = ("closed", "small", "medium", "wide", "round", "teeth")


def _mime(blob: bytes) -> str:
    if blob.startswith(b"\x89PNG"):
        return "image/png"
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _prepare(blob: bytes) -> tuple[bytes, str]:
    image = Image.open(BytesIO(blob)).convert("RGB")
    image.thumbnail((1024, 1024))
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=90)
    data = buf.getvalue()
    return data, "image/jpeg"


def _edit(image_bytes: bytes, prompt: str, api_key: str) -> bytes:
    if not api_key.strip():
        raise RuntimeError("Paste an xAI API key to draw avatars.")
    prepared, mime = _prepare(image_bytes)
    data_url = f"data:{mime};base64," + base64.b64encode(prepared).decode()
    last_error = None
    for model in ("grok-imagine-image-2.0", "grok-imagine-image"):
        body = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "image": {"url": data_url, "type": "image_url"},
                "aspect_ratio": "2:3",
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
            with _open(req, 90) as res:
                payload = json.loads(res.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            last_error = RuntimeError(f"Drawing failed ({exc.code}). {detail}")
            if exc.code != 404:
                raise last_error
            continue
        except Exception as exc:
            raise RuntimeError(f"Drawing did not finish. {exc}") from exc
        item = (payload.get("data") or [{}])[0]
        if item.get("b64_json"):
            drawn = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            with _open(item["url"], 60) as res:
                drawn = res.read()
        else:
            last_error = RuntimeError("No drawing came back. Try again.")
            continue
        if drawn == prepared or drawn == image_bytes:
            last_error = RuntimeError("The picture came back unchanged. Try again.")
            continue
        return drawn
    raise last_error or RuntimeError("No drawing came back. Try again.")


def draw_avatar(photo_path: str, api_key: str, note: str = "") -> bytes:
    extra = f" Extra direction: {note.strip()}" if note.strip() else ""
    photo = Path(photo_path).read_bytes()
    return _edit(photo, AVATAR_PROMPT + extra, api_key)


def draw_background(note: str, api_key: str) -> bytes:
    if not api_key.strip():
        raise RuntimeError("Paste an xAI API key to draw a set.")
    prompt = (
        "Hand-drawn ink and watercolor podcast studio background, wide 16:9, empty of people. "
        "Visible pencil line, soft wash, no text, no watermark, no letters. "
        + (note.strip() or "A warm room with a wooden table and a window.")
    )
    body = json.dumps(
        {
            "model": "grok-imagine-image-2.0",
            "prompt": prompt,
            "response_format": "b64_json",
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.x.ai/v1/images/generations",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key.strip()}",
        },
        method="POST",
    )
    try:
        with _open(req, 180) as res:
            payload = json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"Drawing the set failed ({exc.code}). {detail}") from exc
    item = (payload.get("data") or [{}])[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        with _open(item["url"], 60) as res:
            return res.read()
    raise RuntimeError("No set came back. Try again.")


def draw_mouths(avatar_path: str, api_key: str) -> dict:
    sheet = _edit(Path(avatar_path).read_bytes(), MOUTH_PROMPT, api_key)
    return split_mouth_sheet(sheet)


def parse_mouth_sheet(path, dest_dir) -> dict:
    """Cut a 3-by-2 mouth sheet into the six shapes the scene uses."""
    image = Image.open(path).convert("RGBA")
    width, height = image.size
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    saved = {}
    for index, name in enumerate(MOUTH_NAMES):
        col, row = index % 3, index // 3
        cell = image.crop(
            (
                round(col * width / 3),
                round(row * height / 2),
                round((col + 1) * width / 3),
                round((row + 1) * height / 2),
            )
        )
        cell = _clear_paper(cell)
        box = cell.getbbox()
        if box:
            cell = cell.crop(box)
        file = dest / f"{name}.png"
        cell.save(file, format="PNG")
        saved[name] = str(file)
    return saved


def _clear_paper(cell):
    cell = cell.convert("RGBA")
    width, height = cell.size
    if width < 2 or height < 2:
        return cell
    pixels = cell.load()
    corners = (
        pixels[0, 0],
        pixels[width - 1, 0],
        pixels[0, height - 1],
        pixels[width - 1, height - 1],
    )
    red = sum(color[0] for color in corners) // 4
    green = sum(color[1] for color in corners) // 4
    blue = sum(color[2] for color in corners) // 4

    def paper(x, y):
        pr, pg, pb, _alpha = pixels[x, y]
        return abs(pr - red) < 46 and abs(pg - green) < 46 and abs(pb - blue) < 46

    seen = bytearray(width * height)
    stack = [(x, 0) for x in range(width)]
    stack += [(x, height - 1) for x in range(width)]
    stack += [(0, y) for y in range(height)]
    stack += [(width - 1, y) for y in range(height)]
    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= width or y >= height:
            continue
        mark = y * width + x
        if seen[mark] or not paper(x, y):
            seen[mark] = 1
            continue
        seen[mark] = 1
        pr, pg, pb, _alpha = pixels[x, y]
        pixels[x, y] = (pr, pg, pb, 0)
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return cell


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
