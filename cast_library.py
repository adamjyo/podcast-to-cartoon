"""Saved cast on disk. Avatars stay on this Mac and can be reused."""

from __future__ import annotations

import json
from pathlib import Path

SUPPORT = Path.home() / "Library" / "Application Support" / "PodcastProcessor"
CAST = SUPPORT / "cast"
MOUTH_NAMES = ("closed", "small", "medium", "wide", "round", "teeth")


def _meta_path(folder: Path) -> Path:
    return folder / "meta.json"


def list_cast():
    if not CAST.exists():
        return []
    items = []
    for folder in CAST.iterdir():
        meta = _meta_path(folder)
        if not folder.is_dir() or not meta.exists():
            continue
        data = json.loads(meta.read_text())
        data["id"] = folder.name
        data["folder"] = str(folder)
        data["has_avatar"] = (folder / "avatar.jpg").exists()
        items.append(data)
    items.sort(key=lambda item: item.get("savedAt", 0), reverse=True)
    return items


def load_cast(avatar_id: str):
    folder = CAST / avatar_id
    meta = _meta_path(folder)
    if not meta.exists():
        raise FileNotFoundError(avatar_id)
    data = json.loads(meta.read_text())
    data["id"] = avatar_id
    data["folder"] = str(folder)
    data["photo"] = str(folder / "photo.jpg")
    avatar = folder / "avatar.jpg"
    data["avatar"] = str(avatar) if avatar.exists() else None
    mouths = {}
    mouth_dir = folder / "mouths"
    if mouth_dir.exists():
        for name in MOUTH_NAMES:
            path = mouth_dir / f"{name}.png"
            if path.exists():
                mouths[name] = str(path)
    data["mouths"] = mouths
    return data


def keep_cast(
    avatar_id: str,
    name: str,
    note: str,
    photo: bytes,
    avatar: bytes | None,
    mouth_x: float,
    mouth_y: float,
    mouth_scale: float,
    mouths: dict | None = None,
):
    import time

    folder = CAST / avatar_id
    folder.mkdir(parents=True, exist_ok=True)
    if photo:
        (folder / "photo.jpg").write_bytes(photo)
    if avatar:
        (folder / "avatar.jpg").write_bytes(avatar)
    if mouths:
        mouth_dir = folder / "mouths"
        mouth_dir.mkdir(exist_ok=True)
        for key, blob in mouths.items():
            if key in MOUTH_NAMES and blob:
                (mouth_dir / f"{key}.png").write_bytes(blob)
    payload = {
        "name": name or "Unnamed",
        "note": note or "",
        "mouthX": mouth_x,
        "mouthY": mouth_y,
        "mouthScale": mouth_scale,
        "savedAt": time.time(),
    }
    _meta_path(folder).write_text(json.dumps(payload, indent=2))
    return load_cast(avatar_id)


def forget_cast(avatar_id: str):
    folder = CAST / avatar_id
    if not folder.exists():
        return
    for path in sorted(folder.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    folder.rmdir()
