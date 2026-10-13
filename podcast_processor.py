#!/usr/bin/env python3
"""Mixed podcast audio -> speaker-labeled transcript."""

from __future__ import annotations

import inspect
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

# One OpenMP thread. The speech engine creates its own pool. Setting both
# to every core deadlocks macOS and the bar stays at 6%.
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"


def machine_profile():
    cores = os.cpu_count() or 4
    perf = cores
    ram_gb = 8.0
    chip = platform.machine() or "this computer"
    apple = platform.system() == "Darwin" and platform.machine() == "arm64"
    if platform.system() == "Darwin":
        def sysctl(key):
            try:
                return subprocess.check_output(["sysctl", "-n", key], text=True, timeout=2).strip()
            except Exception:
                return ""

        brand = sysctl("machdep.cpu.brand_string")
        if brand:
            chip = brand
        perf_text = sysctl("hw.perflevel0.physicalcpu")
        if perf_text.isdigit():
            perf = max(1, int(perf_text))
        mem = sysctl("hw.memsize")
        if mem.isdigit():
            ram_gb = int(mem) / (1024 ** 3)
    else:
        try:
            ram_gb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024 ** 3)
        except (ValueError, OSError, AttributeError):
            pass
        brand = platform.processor()
        if brand:
            chip = brand
    if ram_gb < 12:
        batch = 4
    elif ram_gb < 24:
        batch = 8
    else:
        batch = 16
    return {
        "chip": chip,
        "cores": cores,
        "perf": perf,
        "ram_gb": ram_gb,
        "threads": max(2, min(perf, 8)),
        "batch": batch,
        "mps": apple and ram_gb >= 16,
    }


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


def _clear_stale_locks():
    root = Path(os.environ.get("HF_HOME") or (Path.home() / ".cache" / "huggingface"))
    if not root.exists():
        return
    for lock in root.rglob("*.lock"):
        try:
            lock.unlink()
        except OSError:
            pass


def align_model_dir():
    candidates = []
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        candidates.append(Path(bundled) / "align-model")
    candidates.append(Path(__file__).resolve().parent / "vendor" / "align-model")
    for path in candidates:
        if (path / "config.json").is_file():
            return path
    return None


def speech_model_dir():
    candidates = []
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        candidates.append(Path(bundled) / "speech-model")
    candidates.append(Path(__file__).resolve().parent / "vendor" / "speech-model")
    for path in candidates:
        if (path / "model.bin").is_file():
            return path
    return None


def _load_asr(whisperx, threads):
    folder = speech_model_dir()
    if folder is None:
        raise RuntimeError(
            "The speech model is not in this copy of the app. Download the latest Podcast Processor and replace the old one."
        )
    kwargs = {"compute_type": "int8"}
    if _accepts(whisperx.load_model, "threads"):
        kwargs["threads"] = max(1, min(threads, 4))
    if _accepts(whisperx.load_model, "vad_method"):
        kwargs["vad_method"] = "silero"
    saved = os.environ.get("HF_HUB_OFFLINE")
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        return whisperx.load_model(str(folder), "cpu", **kwargs)
    except TypeError:
        kwargs.pop("vad_method", None)
        return whisperx.load_model(str(folder), "cpu", **kwargs)
    finally:
        if saved is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = saved


def _metal_device(profile):
    if not profile["mps"]:
        return "cpu"
    try:
        import torch

        torch.set_num_threads(profile["threads"])
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
    profile = machine_profile()
    hf_token = get_hf_token()
    chip = profile["chip"]
    ram = f"{profile['ram_gb']:.0f} GB"
    tick(0.04, f"This Mac is {chip}, {ram}. Preparing {profile['threads']} cores")
    tick(0.06, "Opening the speech model included with this app")
    model_obj = _load_asr(whisperx, profile["threads"])
    audio = whisperx.load_audio(str(audio_path))
    lang = None if not language or language == "auto" else language

    def listen(pct):
        tick(0.12 + 0.32 * (float(pct) / 100), "Listening for words")

    transcribe_kwargs = {"batch_size": profile["batch"], "language": lang}
    if _accepts(model_obj.transcribe, "progress_callback"):
        transcribe_kwargs["progress_callback"] = listen
    tick(0.12, "Listening for words")
    try:
        result = model_obj.transcribe(audio, **transcribe_kwargs)
    except RuntimeError:
        transcribe_kwargs["batch_size"] = 2
        result = model_obj.transcribe(audio, **transcribe_kwargs)
    if "progress_callback" not in transcribe_kwargs:
        tick(0.44, "Listening for words")
    detected = result.get("language") or language or "en"

    def lined(pct):
        tick(0.46 + 0.2 * (float(pct) / 100), "Lining up each word")

    tick(0.46, "Lining up each word")
    align_kwargs = {}
    bundled_align = align_model_dir()
    if bundled_align is not None:
        align_kwargs["model_name"] = str(bundled_align)
        if _accepts(whisperx.load_align_model, "model_cache_only"):
            align_kwargs["model_cache_only"] = True
    align_model, metadata = whisperx.load_align_model(language_code=detected, device="cpu", **align_kwargs)
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

    voice_device = _metal_device(profile)
    where = "graphics cores" if voice_device == "mps" else f"{profile['threads']} cores"
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
        tick(0.68, f"Telling the voices apart on {profile['threads']} cores")
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


def _pcm(path: Path):
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        tail = (proc.stderr or b"").decode("utf-8", "ignore")[-400:]
        raise RuntimeError(f"Could not read {path.name}. {tail}")
    return proc.stdout


def _speech_spans(raw: bytes):
    import array

    samples = array.array("h")
    samples.frombytes(raw)
    frame = 480
    if len(samples) < frame:
        return []
    loud = []
    for start in range(0, len(samples) - frame, frame):
        acc = 0
        for sample in samples[start : start + frame]:
            acc += sample * sample
        loud.append((acc / frame) ** 0.5)
    ordered = sorted(loud)
    noise = ordered[max(0, int(len(ordered) * 0.6) - 1)] or 1
    gate = max(80, noise * 3.5)
    spans = []
    open_at = None
    for index, level in enumerate(loud):
        if level >= gate and open_at is None:
            open_at = index
        elif level < gate and open_at is not None:
            spans.append((open_at, index))
            open_at = None
    if open_at is not None:
        spans.append((open_at, len(loud)))
    merged = []
    for start, end in spans:
        start_s = start * frame / 16000
        end_s = end * frame / 16000
        if end_s - start_s < 0.25:
            continue
        if merged and start_s - merged[-1][1] < 0.35:
            merged[-1] = (merged[-1][0], end_s)
        else:
            merged.append((start_s, end_s))
    return merged


def _mix_wav(chunks, dest: Path):
    import array
    import wave

    count = max(len(chunk) // 2 for chunk in chunks)
    mix = array.array("h", [0]) * count
    for chunk in chunks:
        track = array.array("h")
        track.frombytes(chunk)
        for index, sample in enumerate(track):
            total = mix[index] + sample
            if total > 32767:
                total = 32767
            elif total < -32768:
                total = -32768
            mix[index] = total
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(mix.tobytes())


def process_tracks(paths, output_dir, progress=None):
    def tick(amount, label):
        if progress:
            progress(amount, label)

    files = [Path(path).expanduser().resolve() for path in paths]
    if not files:
        raise RuntimeError("Choose one audio file for each person.")
    missing = [path.name for path in files if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing audio: " + ", ".join(missing))
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    segments = []
    raw_tracks = []
    per_speaker = {}
    total = len(files)
    for index, path in enumerate(files):
        speaker = path.stem
        tick(0.05 + 0.7 * index / total, f"Reading {speaker}")
        raw = _pcm(path)
        raw_tracks.append(raw)
        per_speaker[speaker] = str(path)
        for start, end in _speech_spans(raw):
            segments.append({"start": start, "end": end, "speaker": speaker, "text": ""})
    if not segments:
        raise RuntimeError("No speech found in those files.")
    segments.sort(key=lambda item: item["start"])
    tick(0.85, "Mixing the tracks")
    mixed = output_dir / "separate-tracks-mix.wav"
    _mix_wav(raw_tracks, mixed)
    result = {
        "segments": segments,
        "language": "en",
        "per_speaker_audio": per_speaker,
        "mixed_audio": str(mixed),
    }
    (output_dir / "separate-tracks.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    tick(1, "Tracks ready")
    return result
