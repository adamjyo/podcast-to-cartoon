"""Mouth cues from the recording, using the bundled Rhubarb Lip Sync binary."""

from __future__ import annotations

import json
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
        return Path(found)
    for root in _search_roots():
        candidate = root / "rhubarb"
        if candidate.is_file():
            return candidate
    return None


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


def _run(binary: Path, wav_path: Path, dialog_path: Path, recognizer: str, out_path: Path):
    cmd = [
        str(binary),
        "-f",
        "json",
        "-r",
        recognizer,
        "--extendedShapes",
        "GHX",
        "--machineReadable",
        "-d",
        str(dialog_path),
        "-o",
        str(out_path),
        str(wav_path),
    ]
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
        dialog_path.write_text(_dialog_text(result), encoding="utf-8")
        _to_wav(Path(audio_path), wav_path)
        tick(0.4, "Matching mouths to the voices")
        try:
            cues = _run(binary, wav_path, dialog_path, recognizer, out_path)
        except RuntimeError:
            if recognizer == "phonetic":
                raise
            cues = _run(binary, wav_path, dialog_path, "phonetic", out_path)
        tick(1, "Mouths matched")
        return cues
    finally:
        shutil.rmtree(work, ignore_errors=True)
