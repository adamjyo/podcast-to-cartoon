"""Mouth cues from the recording, using the bundled Rhubarb Lip Sync binary."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SHAPE_TO_MOUTH = {
    "X": "closed",
    "A": "closed",
    "B": "small",
    "C": "medium",
    "D": "wide",
    "E": "round",
    "F": "round",
    "G": "teeth",
    "H": "medium",
}


def mouth_at(cues, t: float) -> str:
    if not cues:
        return "closed"
    lo, hi = 0, len(cues) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        cue = cues[mid]
        if t < cue["start"]:
            hi = mid - 1
        elif t >= cue["end"]:
            lo = mid + 1
        else:
            return cue["mouth"]
    return "closed"


def _search_roots():
    roots = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        roots.extend(
            [
                exe.parent,
                exe.parent / "Resources",
                exe.parent.parent / "Resources",
                exe.parent.parent / "Frameworks",
            ]
        )
    here = Path(__file__).resolve().parent
    roots.extend([here, here / "vendor" / "rhubarb"])
    return roots


def find_rhubarb():
    found = shutil.which("rhubarb")
    if found:
        binary = Path(found)
        _place_res(binary)
        return binary
    names = ("rhubarb", "rhubarb.exe")
    candidates = []
    for root in _search_roots():
        for name in names:
            candidates.append(root / name)
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        for folder in (exe.parent, exe.parent / "_internal", exe.parent.parent / "Frameworks", exe.parent.parent / "Resources"):
            for name in names:
                candidates.append(folder / name)
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            _place_res(candidate)
            return candidate
    return None


def _place_res(binary: Path):
    beside = binary.parent / "res"
    if any(beside.glob("*")) if beside.is_dir() else False:
        return
    sources = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        sources.append(Path(meipass) / "res")
    sources.append(binary.parent.parent / "Resources" / "res")
    sources.append(binary.parent / "_internal" / "res")
    for source in sources:
        if source.is_dir() and any(source.iterdir()):
            beside.mkdir(parents=True, exist_ok=True)
            for item in source.iterdir():
                dest = beside / item.name
                if dest.exists():
                    continue
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            return


def _dialog_text(result) -> str:
    parts = []
    for seg in result.get("segments") or []:
        text = (seg.get("text") or "").strip()
        if text:
            parts.append(text)
    return " ".join(parts)


def _to_wav(audio_path: Path, wav_path: Path):
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(audio_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(wav_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not wav_path.exists():
        tail = (proc.stderr or "")[-800:]
        raise RuntimeError(f"Could not prepare audio for lip sync. {tail}")


def _run(binary: Path, wav_path: Path, dialog_path: Path, recognizer: str, out_path: Path, use_dialog: bool):
    cmd = [
        str(binary),
        "-f",
        "json",
        "-r",
        recognizer,
        "--extendedShapes",
        "GHX",
        "--machineReadable",
    ]
    if use_dialog:
        cmd.extend(["-d", str(dialog_path)])
    cmd.extend(["-o", str(out_path), str(wav_path)])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_path.exists():
        tail = ((proc.stderr or "") + "\n" + (proc.stdout or ""))[-800:]
        raise RuntimeError(tail.strip() or f"Rhubarb exited {proc.returncode}")
    payload = json.loads(out_path.read_text())
    cues = []
    for cue in payload.get("mouthCues") or []:
        shape = str(cue.get("value") or "X").upper()
        cues.append(
            {
                "start": float(cue.get("start") or 0),
                "end": float(cue.get("end") or 0),
                "mouth": SHAPE_TO_MOUTH.get(shape, "medium"),
            }
        )
    cues.sort(key=lambda item: item["start"])
    return cues


def build_cues(audio_path: str, result, progress=None) -> list:
    def tick(amount, label):
        if progress:
            progress(amount, label)

    binary = find_rhubarb()
    if binary is None:
        raise RuntimeError("Rhubarb Lip Sync is not in this app build.")
    language = (result.get("language") or "en").lower()
    recognizer = "pocketSphinx" if language.startswith("en") else "phonetic"
    work = Path(tempfile.mkdtemp(prefix="podcast-lipsync-"))
    try:
        wav_path = work / "speech.wav"
        dialog_path = work / "dialog.txt"
        out_path = work / "cues.json"
        tick(0.12, "Preparing the recording")
        dialog = _dialog_text(result)
        dialog_path.write_text(dialog, encoding="utf-8")
        _to_wav(Path(audio_path), wav_path)
        recognizer = "phonetic" if not dialog else recognizer
        tick(0.4, "Rhubarb is matching the mouths")
        try:
            cues = _run(binary, wav_path, dialog_path, recognizer, out_path, bool(dialog))
        except RuntimeError:
            if recognizer == "phonetic":
                raise
            cues = _run(binary, wav_path, dialog_path, "phonetic", out_path, False)
        tick(1, "Mouths matched")
        return cues
    finally:
        shutil.rmtree(work, ignore_errors=True)
