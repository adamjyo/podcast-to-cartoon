#!/usr/bin/env python3
"""Mixed podcast audio -> speaker-labeled transcript."""

import json
import os
from pathlib import Path


def get_hf_token():
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if not token:
        raise RuntimeError(
            "Hugging Face token required. Paste it in the app, or set HF_TOKEN."
        )
    return token


def process_audio(
    audio_path: str,
    output_dir: str,
    model: str = "medium",
    min_speakers: int = 4,
    max_speakers: int = 5,
    language: str = "en",
    device: str = None,
):
    try:
        import whisperx
    except ImportError as exc:
        raise RuntimeError(
            "The speech engine is missing from this app build."
        ) from exc

    audio_path = Path(audio_path).expanduser().resolve()
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if device is None or device == "auto":
        device = "cpu"
        try:
            import torch

            if torch.backends.mps.is_available():
                device = "cpu"
        except Exception:
            device = "cpu"

    hf_token = get_hf_token()
    compute_type = "float16" if device == "cuda" else "int8"

    model_obj = whisperx.load_model(model, device, compute_type=compute_type)
    audio = whisperx.load_audio(str(audio_path))
    lang = None if not language or language == "auto" else language
    result = model_obj.transcribe(audio, batch_size=4, language=lang)

    detected = result.get("language") or language or "en"
    align_model, metadata = whisperx.load_align_model(
        language_code=detected, device=device
    )
    result = whisperx.align(
        result["segments"],
        align_model,
        metadata,
        audio,
        device,
        return_char_alignments=False,
    )

    try:
        diarize_model = whisperx.DiarizationPipeline(token=hf_token, device=device)
    except TypeError:
        diarize_model = whisperx.DiarizationPipeline(
            use_auth_token=hf_token, device=device
        )
    diarize_segments = diarize_model(
        audio, min_speakers=min_speakers, max_speakers=max_speakers
    )
    result = whisperx.assign_word_speakers(diarize_segments, result)

    base_name = audio_path.stem
    json_path = output_dir / f"{base_name}_diarized.json"
    json_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    srt_path = output_dir / f"{base_name}_speakers.srt"
    write_srt(result, srt_path)
    summary_path = output_dir / f"{base_name}_summary.txt"
    write_summary(result, summary_path)
    return result


def write_srt(result, path: Path):
    lines = []
    idx = 1
    for seg in result.get("segments", []):
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        speaker = seg.get("speaker") or "UNKNOWN"
        lines.append(str(idx))
        lines.append(
            f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}"
        )
        lines.append(f"[{speaker}] {text}")
        lines.append("")
        idx += 1
    path.write_text("\n".join(lines), encoding="utf-8")


def write_summary(result, path: Path):
    lines = ["# Speaker Summary", ""]
    current = None
    buffer = []
    for seg in result.get("segments", []):
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        speaker = seg.get("speaker") or "UNKNOWN"
        if speaker != current:
            if buffer:
                lines.append(f"**{current}**: {' '.join(buffer)}")
                lines.append("")
            current = speaker
            buffer = [text]
        else:
            buffer.append(text)
    if buffer:
        lines.append(f"**{current}**: {' '.join(buffer)}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def format_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def speakers_in(result):
    found = []
    for seg in result.get("segments", []):
        name = seg.get("speaker")
        if name and name not in found:
            found.append(name)
    return found
