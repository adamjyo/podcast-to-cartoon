#!/usr/bin/env python3
"""Mixed podcast audio -> speaker-labeled transcript."""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

_CORES = os.cpu_count() or 4
os.environ["OMP_NUM_THREADS"] = str(_CORES)
os.environ["MKL_NUM_THREADS"] = str(_CORES)
os.environ["VECLIB_MAXIMUM_THREADS"] = str(_CORES)
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"


def get_hf_token():
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if not token:
        raise RuntimeError("Hugging Face token required. Paste it in the app.")
    return token


def _accepts(fn, name):
    try:
        return name in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def _load_asr(whisperx, model, threads):
    kwargs = {"compute_type": "int8"}
    if _accepts(whisperx.load_model, "threads"):
        kwargs["threads"] = threads
    return whisperx.load_model(model, "cpu", **kwargs)


def _metal_device():
    try:
        import torch

        torch.set_num_threads(_CORES)
        if hasattr(torch, "set_float32_matmul_precision"):
            torch.set_float32_matmul_precision("high")
        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


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
    hf_token = get_hf_token()
    voice_device = _metal_device()
    tick(0.06, f"Opening the recording on {_CORES} cores")
    model_obj = _load_asr(whisperx, model, _CORES)
    audio = whisperx.load_audio(str(audio_path))
    lang = None if not language or language == "auto" else language

    def listen(pct):
        tick(0.1 + 0.34 * (float(pct) / 100), "Listening for words")

    transcribe_kwargs = {"batch_size": 16, "language": lang}
    if _accepts(model_obj.transcribe, "progress_callback"):
        transcribe_kwargs["progress_callback"] = listen
    tick(0.1, "Listening for words")
    try:
        result = model_obj.transcribe(audio, **transcribe_kwargs)
    except RuntimeError:
        transcribe_kwargs["batch_size"] = 4
        result = model_obj.transcribe(audio, **transcribe_kwargs)
    if "progress_callback" not in transcribe_kwargs:
        tick(0.44, "Listening for words")
    detected = result.get("language") or language or "en"

    def lined(pct):
        tick(0.46 + 0.2 * (float(pct) / 100), "Lining up each word")

    tick(0.46, "Lining up each word")
    align_model, metadata = whisperx.load_align_model(language_code=detected, device="cpu")
    align_kwargs = {}
    if _accepts(whisperx.align, "progress_callback"):
        align_kwargs["progress_callback"] = lined
    result = whisperx.align(
        result["segments"],
        align_model,
        metadata,
        audio,
        "cpu",
        return_char_alignments=False,
        **align_kwargs,
    )

    def voices(pct):
        tick(0.68 + 0.24 * (float(pct) / 100), "Telling the voices apart")

    where = "graphics cores" if voice_device == "mps" else f"{_CORES} cores"
    tick(0.68, f"Telling the voices apart on the {where}")

    def diarize(on_device):
        try:
            pipe = whisperx.DiarizationPipeline(token=hf_token, device=on_device)
        except TypeError:
            pipe = whisperx.DiarizationPipeline(use_auth_token=hf_token, device=on_device)
        kwargs = {"min_speakers": min_speakers, "max_speakers": max_speakers}
        if _accepts(pipe.__call__, "progress_callback"):
            kwargs["progress_callback"] = voices
        return pipe(audio, **kwargs)

    try:
        diarize_segments = diarize(voice_device)
    except Exception:
        if voice_device == "cpu":
            raise
        tick(0.68, f"Telling the voices apart on {_CORES} cores")
        diarize_segments = diarize("cpu")
    result = whisperx.assign_word_speakers(diarize_segments, result)

    tick(0.94, "Saving the transcript")
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
