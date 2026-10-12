"""Hand-drawn stage. Uses a saved avatar when one is assigned, otherwise a simple card."""

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from rhubarb_sync import mouth_at

W, H = 1280, 720
FPS = 4
PALETTE = [("#2f5d50", "#e7f2ec"), ("#8c4a32", "#f8ebe4"), ("#3d4c7a", "#e8ecf8"), ("#7a6232", "#f7f1e2"), ("#6b3d62", "#f6eaf3")]
TALK = ("small", "medium", "wide", "medium", "round", "teeth", "small")


def _font(size):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _active(segments, t):
    for seg in segments:
        if seg.get("start", 0) <= t < seg.get("end", 0):
            return seg
    return None


def _wrap(draw, text, font, width):
    words = (text or "").split()
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else f"{cur} {word}"
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines[:3]


def _stock_mouth(name):
    img = Image.new("RGBA", (180, 120), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    ink = (40, 28, 22, 255)
    if name == "closed":
        draw.arc((30, 40, 150, 90), 15, 165, fill=ink, width=6)
    elif name == "small":
        draw.ellipse((60, 45, 120, 80), outline=ink, width=6)
    elif name == "wide":
        draw.ellipse((25, 30, 155, 100), fill=(90, 40, 40, 255), outline=ink, width=5)
    elif name == "round":
        draw.ellipse((55, 25, 125, 100), outline=ink, width=6)
    elif name == "teeth":
        draw.rectangle((40, 40, 140, 85), outline=ink, width=5)
        draw.line((40, 58, 140, 58), fill=ink, width=3)
    else:
        draw.ellipse((45, 35, 135, 95), outline=ink, width=6)
    return img


def _mouth_image(cast, name):
    custom = (cast or {}).get("mouths") or {}
    path = custom.get(name)
    if path and Path(path).exists():
        return Image.open(path).convert("RGBA")
    return _stock_mouth(name)


def _card(cast, label, ink, fill, talking_shape):
    card = Image.new("RGBA", (360, 460), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((8, 8, 352, 452), radius=28, fill=fill, outline=ink, width=6)
    portrait_path = (cast or {}).get("avatar") or (cast or {}).get("photo")
    if portrait_path and Path(portrait_path).exists():
        portrait = Image.open(portrait_path).convert("RGBA")
        portrait.thumbnail((300, 340))
        px = (360 - portrait.width) // 2
        py = 28
        card.paste(portrait, (px, py), portrait)
        mouth = _mouth_image(cast, talking_shape)
        scale = float((cast or {}).get("mouthScale") or 22) / 100
        mw = max(24, int(portrait.width * scale))
        mh = max(16, int(mouth.height * mw / max(1, mouth.width)))
        mouth = mouth.resize((mw, mh), Image.LANCZOS)
        mx = px + int(portrait.width * float((cast or {}).get("mouthX") or 50) / 100) - mw // 2
        my = py + int(portrait.height * float((cast or {}).get("mouthY") or 64) / 100) - mh // 2
        card.paste(mouth, (mx, my), mouth)
    else:
        draw.ellipse((120, 70, 240, 200), outline=ink, width=4)
        if talking_shape == "closed":
            draw.arc((150, 150, 210, 180), 10, 170, fill=ink, width=3)
        else:
            draw.ellipse((155, 145, 205, 185), fill=ink)
    name_font = _font(22)
    draw.text((24, 400), (label or "")[:22], font=name_font, fill=ink)
    return card


def render_cartoon(result, audio_path, out_path, names, cast_for_speaker=None, progress=None, cues=None):
    import imageio_ffmpeg

    segments = result.get("segments") or []
    if not segments:
        raise RuntimeError("No speech found to animate.")
    speakers = []
    for seg in segments:
        sp = seg.get("speaker") or "UNKNOWN"
        if sp not in speakers:
            speakers.append(sp)
    labels = {sp: (names.get(sp) or sp) for sp in speakers}
    cast_for_speaker = cast_for_speaker or {}
    end = max(float(seg.get("end") or 0) for seg in segments)
    nframes = max(1, int(end * FPS) + 1)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-", "-i", str(audio_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    title_font = _font(28)
    sub_font = _font(26)
    try:
        for i in range(nframes):
            t = i / FPS
            img = Image.new("RGB", (W, H), "#f3ecdf")
            draw = ImageDraw.Draw(img)
            draw.rectangle((0, 0, W, 86), fill="#1f2a24")
            draw.text((36, 26), "Podcast cartoon", font=title_font, fill="#f6f1e7")
            seg = _active(segments, t)
            active = (seg or {}).get("speaker")
            n = max(1, len(speakers))
            gap = 24
            card_w = min(360, int((W - 80 - gap * (n - 1)) / n))
            total = n * card_w + (n - 1) * gap
            x0 = (W - total) // 2
            for idx, sp in enumerate(speakers):
                ink, fill = PALETTE[idx % len(PALETTE)]
                talking = mouth_at(cues, t) if sp == active and cues else ("closed" if sp != active else TALK[(i // 2) % len(TALK)])
                card = _card(cast_for_speaker.get(sp), labels[sp], ink, fill, talking)
                card = card.resize((card_w, int(card.height * card_w / card.width)), Image.LANCZOS)
                img.paste(card, (x0 + idx * (card_w + gap), 100), card)
            draw.rounded_rectangle((60, 580, W - 60, 690), radius=18, fill="#fffaf3", outline="#1f2a24", width=3)
            text = ((seg or {}).get("text") or "").strip()
            who = labels.get(active, "")
            if who and text:
                text = f"{who}: {text}"
            for nline, line in enumerate(_wrap(draw, text or "...", sub_font, W - 180)):
                draw.text((90, 596 + nline * 30), line, font=sub_font, fill="#1f2a24")
            proc.stdin.write(img.convert("RGB").tobytes())
            if progress and i % FPS == 0:
                progress(i + 1, nframes)
    finally:
        if proc.stdin:
            proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
        code = proc.wait()
    if code != 0:
        raise RuntimeError(err[-1500:] or f"ffmpeg exited {code}")
    return out_path
