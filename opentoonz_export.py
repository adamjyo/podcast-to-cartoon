"""Write an OpenToonz folder: one mouth level and lip-sync file per speaker."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image

from podcast_video import _mouth_image
from rhubarb_sync import mouth_at

FPS = 24
MOUTH_TO_SHAPE = {
    "closed": "X",
    "small": "B",
    "medium": "C",
    "wide": "D",
    "round": "E",
    "teeth": "G",
}


def find_opentoonz():
    roots = [Path("/Applications"), Path.home() / "Applications"]
    found = []
    for root in roots:
        if not root.exists():
            continue
        found.extend(root.glob("OpenToonz*.app"))
        found.extend(root.glob("*/OpenToonz*.app"))
    return found[0] if found else None


def _safe(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in (name or "speaker"))
    return cleaned.strip("_") or "speaker"


def _active_speaker(segments, t):
    for seg in segments:
        if float(seg.get("start") or 0) <= t < float(seg.get("end") or 0):
            return seg.get("speaker")
    return None


def _dat(segments, speaker, cues, frames):
    lines = ["MohoSwitch1"]
    current = None
    for frame in range(1, frames + 1):
        t = (frame - 1) / FPS
        if _active_speaker(segments, t) == speaker:
            shape = MOUTH_TO_SHAPE.get(mouth_at(cues, t), "C")
        else:
            shape = "X"
        if shape != current:
            lines.append(f"{frame} {shape}")
            current = shape
    return "\n".join(lines) + "\n"


def export_opentoonz(audio, result, names, cast_for_speaker, cues, dest_dir):
    dest = Path(dest_dir)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    audio_path = Path(audio)
    shutil.copy2(audio_path, dest / audio_path.name)
    segments = result.get("segments") or []
    end = max((float(seg.get("end") or 0) for seg in segments), default=1)
    frames = max(1, int(end * FPS) + 1)
    speakers = []
    for seg in segments:
        name = seg.get("speaker")
        if name and name not in speakers:
            speakers.append(name)
    for speaker in speakers:
        label = names.get(speaker) or speaker
        safe = _safe(label)
        folder = dest / safe
        folder.mkdir()
        cast = (cast_for_speaker or {}).get(speaker)
        portrait = (cast or {}).get("avatar") or (cast or {}).get("photo")
        if portrait and Path(portrait).exists():
            Image.open(portrait).convert("RGBA").save(folder / f"{safe}_portrait.png")
        for mouth, shape in MOUTH_TO_SHAPE.items():
            picture = _mouth_image(cast, mouth)
            picture.save(folder / f"{safe}.{shape}.png")
        (folder / f"{safe}.dat").write_text(_dat(segments, speaker, cues, frames), encoding="utf-8")
    return dest


def launch_opentoonz(dest):
    app = find_opentoonz()
    if app is None:
        return None
    subprocess.Popen(["open", "-a", str(app), str(dest)])
    return app
