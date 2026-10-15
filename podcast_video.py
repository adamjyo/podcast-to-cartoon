"""Hand-drawn stage. Uses a saved avatar when one is assigned, otherwise a simple card."""

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from rhubarb_sync import mouth_at
from stage import paint_stage

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


def preview_puppet(cast, shape="closed"):
    card = _card(cast, (cast or {}).get("name") or "", "#1f2a24", "#fffaf3", shape)
    card.thumbnail((240, 320))
    return card


def render_cartoon(result, audio_path, out_path, names, cast_for_speaker=None, progress=None, cues=None, background=None):
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
    plate = paint_stage(background, (W, H))
    try:
        for i in range(nframes):
            t = i / FPS
            img = plate.copy()
            draw = ImageDraw.Draw(img)
            draw.rectangle((0, 0, W, 86), fill="#1f2a24")
            draw.text((36, 26), "Podcast cartoon", font=title_font, fill="#f6f1e7")
            seg = _active(segments, t)
            active = (seg or {}).get("speaker")
            n = max(1, len(speakers))
            gap = 24
            scales = []
            for sp in speakers:
                raw = float((cast_for_speaker.get(sp) or {}).get("puppetScale") or 1)
                scales.append(min(1.6, max(0.55, raw)))
            available = W - 80 - gap * (n - 1)
            widths = [max(140, int(available * scale / sum(scales))) for scale in scales]
            x = (W - (sum(widths) + gap * (n - 1))) // 2
            for idx, sp in enumerate(speakers):
                ink, fill = PALETTE[idx % len(PALETTE)]
                if isinstance(cues, dict):
                    talking = mouth_at(cues.get(sp) or [], t)
                elif sp == active and cues:
                    talking = mouth_at(cues, t)
                else:
                    talking = "closed" if sp != active else TALK[(i // 2) % len(TALK)]
                card = _card(cast_for_speaker.get(sp), labels[sp], ink, fill, talking)
                card_w = widths[idx]
                card = card.resize((card_w, int(card.height * card_w / card.width)), Image.LANCZOS)
                img.paste(card, (x, 100), card)
                x += card_w + gap
            draw.rounded_rectangle((60, 580, W - 60, 690), radius=18, fill="#fffaf3", outline="#1f2a24", width=3)
            text = ((seg or {}).get("text") or "").strip()
            who = labels.get(active, "")
            if who and text:
                text = f"{who}: {text}"
            for nline, line in enumerate(_wrap(draw, text or "...", sub_font, W - 180)):
                draw.text((90, 596 + nline * 30), line, font=sub_font, fill="#1f2a24")
            proc.stdin.write(img.convert("RGB").tobytes())
            if progress and (i % FPS == 0 or i == nframes - 1):
                progress(i + 1, nframes)
    finally:
        if proc.stdin:
            proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
        code = proc.wait()
    if code != 0:
        raise RuntimeError(err[-1500:] or f"ffmpeg exited {code}")
    return out_path


def shot_at(cuts, t):
    shot = "wide"
    for cut in cuts or []:
        if float(cut.get("t") or 0) <= float(t) + 0.001:
            shot = cut.get("shot") or "wide"
        else:
            break
    return shot


def camera_for(shot, people, width, height):
    if shot == "wide":
        return 1.0, 0.0, 0.0
    person = next((item for item in people if item.get("name") == shot and item.get("image")), None)
    image = (person or {}).get("image")
    if not person or not image or not Path(image).exists():
        return 1.0, 0.0, 0.0
    with Image.open(image) as picture:
        aspect = picture.width / max(1, picture.height)
    ph = max(48, int(float(person.get("h") or 0.7) * height))
    pw = max(24, int(ph * aspect))
    px = float(person.get("x") or 0) * width
    py = float(person.get("y") or 0) * height
    zoom = min(3.4, max(1.15, height / (ph * 0.62)))
    pan_x = (px + pw * 0.5) - (width / 2) / zoom
    pan_y = (py + ph * 0.30) - (height / 2) / zoom
    return zoom, pan_x, pan_y


def _blit(canvas, picture, x, y, w, h, zoom, pan_x, pan_y):
    sw = max(1, int(w * zoom))
    sh = max(1, int(h * zoom))
    sx = int((x - pan_x) * zoom)
    sy = int((y - pan_y) * zoom)
    resized = picture.resize((sw, sh), Image.LANCZOS)
    canvas.paste(resized, (sx, sy), resized)


def _broadcast_frame(people, background, t, cuts, cues, width, height):
    zoom, pan_x, pan_y = camera_for(shot_at(cuts, t), people, width, height)
    canvas = Image.new("RGBA", (width, height), (28, 36, 32, 255))
    _blit(canvas, background, 0, 0, width, height, zoom, pan_x, pan_y)
    for person in people:
        image = person.get("image")
        if not image or not Path(image).exists():
            continue
        body = Image.open(image).convert("RGBA")
        ph = max(48, int(float(person.get("h") or 0.7) * height))
        pw = max(24, int(ph * body.width / max(1, body.height)))
        portrait = body.resize((pw, ph), Image.LANCZOS)
        shape = mouth_at((cues or {}).get(person.get("name")) or [], t)
        mouths = person.get("mouths") or {}
        mouth_path = mouths.get(shape) or mouths.get("closed") or ""
        if mouth_path and Path(mouth_path).exists():
            mouth = Image.open(mouth_path).convert("RGBA")
            mw = max(12, int(pw * float(person.get("mouthScale") or 18) / 100))
            mh = max(8, int(mouth.height * mw / max(1, mouth.width)))
            mouth = mouth.resize((mw, mh), Image.LANCZOS)
            ox = int(pw * float(person.get("mouthX") or 50) / 100) - mw // 2
            oy = int(ph * float(person.get("mouthY") or 42) / 100) - mh // 2
            portrait.paste(mouth, (ox, oy), mouth)
        _blit(
            canvas,
            portrait,
            float(person.get("x") or 0) * width,
            float(person.get("y") or 0) * height,
            pw,
            ph,
            zoom,
            pan_x,
            pan_y,
        )
    draw = ImageDraw.Draw(canvas)
    tx = int((0 - pan_x) * zoom)
    ty = int((height * 0.68 - pan_y) * zoom)
    tw = max(1, int(width * zoom))
    th = max(1, int(height * 0.34 * zoom))
    draw.rectangle((tx, ty, tx + tw, ty + max(8, int(th * 0.16))), fill="#c4a27a")
    draw.rectangle((tx, ty + int(th * 0.12), tx + tw, ty + th + 8), fill="#6b4228")
    return canvas.convert("RGB")


def render_broadcast(people, cuts, cues, out_path, background=None, audio_path=None, duration=8, progress=None, fps=12):
    import imageio_ffmpeg

    width, height = W, H
    if background and Path(str(background)).exists():
        plate = paint_stage({"image": str(background)}, (width, height)).convert("RGBA")
    else:
        plate = paint_stage({"preset": background or "coffee shop"}, (width, height)).convert("RGBA")
    duration = max(1.0, float(duration or 1))
    nframes = max(1, int(duration * fps))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
        "-r", str(fps), "-i", "-",
    ]
    if audio_path and Path(audio_path).exists():
        cmd += ["-i", str(audio_path), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"]
    else:
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    cmd.append(str(out_path))
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(nframes):
            frame = _broadcast_frame(people, plate, i / fps, cuts, cues, width, height)
            proc.stdin.write(frame.tobytes())
            if progress and (i % fps == 0 or i == nframes - 1):
                progress(i + 1, nframes)
    finally:
        if proc.stdin:
            proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
        code = proc.wait()
    if code != 0:
        raise RuntimeError(err[-1500:] or f"ffmpeg exited {code}")
    return out_path
