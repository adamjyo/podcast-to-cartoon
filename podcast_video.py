"""Simple hand-drawn style video from diarized transcript."""

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H = 1280, 720
FPS = 4
PALETTE = [
    ("#2f5d50", "#e7f2ec"),
    ("#8c4a32", "#f8ebe4"),
    ("#3d4c7a", "#e8ecf8"),
    ("#7a6232", "#f7f1e2"),
    ("#6b3d62", "#f6eaf3"),
    ("#2f5f6b", "#e5f3f6"),
]


def _font(size):
    for path in (
        "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
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
    words = text.split()
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


def render_cartoon(result, audio_path, out_path, names, progress=None):
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

    end = max(float(seg.get("end") or 0) for seg in segments)
    nframes = max(1, int(end * FPS) + 1)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    title_font = _font(28)
    name_font = _font(22)
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
            gap = 36
            card_w = min(220, int((W - 80 - gap * (n - 1)) / n))
            total = n * card_w + (n - 1) * gap
            x0 = (W - total) // 2
            for idx, sp in enumerate(speakers):
                ink, fill = PALETTE[idx % len(PALETTE)]
                x = x0 + idx * (card_w + gap)
                y = 150
                outline = 8 if sp == active else 3
                draw.rounded_rectangle(
                    (x, y, x + card_w, y + 280),
                    radius=28,
                    fill=fill,
                    outline=ink,
                    width=outline,
                )
                cx = x + card_w // 2
                draw.ellipse((cx - 54, y + 36, cx + 54, y + 150), outline=ink, width=4)
                draw.ellipse((cx - 28, y + 70, cx - 12, y + 86), fill=ink)
                draw.ellipse((cx + 12, y + 70, cx + 28, y + 86), fill=ink)
                if sp == active:
                    draw.ellipse((cx - 22, y + 104, cx + 22, y + 136), fill=ink)
                else:
                    draw.arc((cx - 18, y + 108, cx + 18, y + 132), 10, 170, fill=ink, width=3)
                label = labels[sp]
                draw.text((x + 16, y + 230), label[:16], font=name_font, fill=ink)

            draw.rounded_rectangle((60, 500, W - 60, 660), radius=18, fill="#fffaf3", outline="#1f2a24", width=3)
            text = ((seg or {}).get("text") or "").strip()
            who = labels.get(active, "")
            if who and text:
                text = f"{who}: {text}"
            dummy = ImageDraw.Draw(img)
            lines = _wrap(dummy, text or "...", sub_font, W - 180)
            yy = 524
            for line in lines:
                draw.text((90, yy), line, font=sub_font, fill="#1f2a24")
                yy += 36

            proc.stdin.write(img.tobytes())
            if progress and i % FPS == 0:
                progress(i + 1, nframes)
    finally:
        if proc.stdin:
            proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
        code = proc.wait()
    if code != 0:
        raise RuntimeError(err[-2000:] or f"ffmpeg exited {code}")
    return out_path
