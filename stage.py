"""Hand-drawn stage backgrounds. Saved sets stay on this Mac."""

from __future__ import annotations

import json
import time
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from cast_library import SUPPORT

SETS = SUPPORT / "backgrounds"
PRESETS = ("paper", "studio", "bookshelf", "night window")


def paint_stage(spec, size=(1280, 720)):
    spec = spec or {}
    image = spec.get("image")
    if image and Path(image).exists():
        picture = Image.open(image).convert("RGB")
        return _cover(picture, size)
    return _preset(spec.get("preset") or "paper", size)


def _cover(picture, size):
    tw, th = size
    scale = max(tw / picture.width, th / picture.height)
    resized = picture.resize((max(1, int(picture.width * scale)), max(1, int(picture.height * scale))), Image.LANCZOS)
    left = max(0, (resized.width - tw) // 2)
    top = max(0, (resized.height - th) // 2)
    return resized.crop((left, top, left + tw, top + th))


def _preset(name, size):
    w, h = size
    if name == "studio":
        img = Image.new("RGB", size, "#efe2cf")
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, int(h * 0.72), w, h), fill="#8c5a3c")
        draw.rectangle((0, int(h * 0.70), w, int(h * 0.74)), fill="#5c3b28")
        draw.ellipse((w // 2 - 180, int(h * 0.62), w // 2 + 180, int(h * 0.95)), fill="#c9845a")
        draw.rectangle((90, 70, 250, 220), outline="#1f2a24", width=6)
        draw.rectangle((w - 280, 60, w - 70, 240), outline="#1f2a24", width=6)
        return img
    if name == "bookshelf":
        img = Image.new("RGB", size, "#f4eadb")
        draw = ImageDraw.Draw(img)
        colors = ("#2f5d50", "#8c4a32", "#3d4c7a", "#7a6232", "#6b3d62", "#c45c26")
        for shelf in range(4):
            y = 40 + shelf * (h // 5)
            draw.rectangle((30, y + 110, w - 30, y + 124), fill="#5c3b28")
            x = 50
            i = 0
            while x < w - 70:
                bw = 28 + ((i * 17) % 24)
                draw.rectangle((x, y + 20, x + bw, y + 110), fill=colors[(shelf + i) % len(colors)])
                x += bw + 6
                i += 1
        return img
    if name == "night window":
        img = Image.new("RGB", size, "#243044")
        draw = ImageDraw.Draw(img)
        draw.rectangle((70, 50, 430, 420), fill="#d7e4ef", outline="#1f2a24", width=10)
        draw.line((250, 50, 250, 420), fill="#1f2a24", width=8)
        draw.line((70, 230, 430, 230), fill="#1f2a24", width=8)
        draw.ellipse((w - 280, h - 260, w - 40, h - 20), fill="#e7b15a")
        draw.rectangle((0, int(h * 0.78), w, h), fill="#1b242c")
        return img
    img = Image.new("RGB", size, "#f3ecdf")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, w, 8), fill="#e4d8c6")
    return img


def list_sets():
    if not SETS.exists():
        return []
    items = []
    for folder in SETS.iterdir():
        meta_path = folder / "meta.json"
        if not folder.is_dir() or not meta_path.exists():
            continue
        data = json.loads(meta_path.read_text())
        data["id"] = folder.name
        data["image"] = str(folder / "background.jpg") if (folder / "background.jpg").exists() else None
        items.append(data)
    items.sort(key=lambda item: item.get("savedAt", 0), reverse=True)
    return items


def load_set(set_id: str):
    folder = SETS / set_id
    meta_path = folder / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(set_id)
    data = json.loads(meta_path.read_text())
    data["id"] = set_id
    picture = folder / "background.jpg"
    data["image"] = str(picture) if picture.exists() else None
    return data


def keep_set(set_id: str, name: str, preset: str, image: bytes | None = None):
    folder = SETS / set_id
    folder.mkdir(parents=True, exist_ok=True)
    if image:
        (folder / "background.jpg").write_bytes(image)
    else:
        painted = paint_stage({"preset": preset})
        buf = BytesIO()
        painted.save(buf, format="JPEG", quality=85)
        (folder / "background.jpg").write_bytes(buf.getvalue())
    payload = {"name": name or preset, "preset": preset, "savedAt": time.time()}
    (folder / "meta.json").write_text(json.dumps(payload, indent=2))
    return load_set(set_id)


def forget_set(set_id: str):
    folder = SETS / set_id
    if not folder.exists():
        return
    for path in sorted(folder.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    folder.rmdir()
