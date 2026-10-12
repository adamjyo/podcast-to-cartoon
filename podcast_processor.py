#!/usr/bin/env python3
"""Mixed podcast audio -> speaker-labeled transcript."""

from __future__ import annotations

import json
import os
from pathlib import Path


def get_hf_token():
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if not token:
        raise RuntimeError("Hugging Face token required. Paste it in the app.")
    return token


def process_audio(
    audio_path: str,
    output_dir: str,
    model: str = "small",
    min_speakers: int = 4,
    max_speakers: int = 5,
    language: str = "en",
    device: str = None,
    progress=None,
):
    def tick(amount, label):
        if progress:
            progress(amount, label)

    try:
        import whisperx
    except ImportError as exc:
        raise RuntimeError("The speech engine is missing from this app build.") from exc

    audio_path = Path(audio_path).expanduser().resolve()
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    device = "cpu"
    hf_token = get_hf_token()
    compute_type = "int8"
    tick(0.08, "Opening the recording")
    model_obj = whisperx.load_model(model, device, compute_type=compute_type)
    audio = whisperx.load_audio(str(audio_path))
    lang = None if not language or language == "auto" else language
    tick(0.22, "Listening for words")
    result = model_obj.transcribe(audio, batch_size=4, language=lang)
    detected = result.get("language") or language or "en"
    tick(0.5, "Lining up each word")
    align_model, metadata = whisperx.load_align_model(language_code=detected, device=device)
    result = whisperx.align(
        result["segments"], align_model, metadata, audio, device, return_char_alignments=False
    )
    tick(0.7, "Telling the voices apart")
    try:
        diarize_model = whisperx.DiarizationPipeline(token=hf_token, device=device)
    except TypeError:
        diarize_model = whisperx.DiarizationPipeline(use_auth_token=hf_token, device=device)
    diarize_segments = diarize_model(audio, min_speakers=min_speakers, max_speakers=max_speakers)
    result = whisperx.assign_word_speakers(diarize_segments, result)

    tick(0.92, "Saving the transcript")
    base = audio_path.stem
    (output_dir / f"{base}_diarized.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    tick(1, "Speakers found")
    return result


def speakers_in(result):
    found = []
    for seg in result.get("segments", []):
        name = seg.get("speaker")
        if name and name not in found:
            found.append(name)
    return found
