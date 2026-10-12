#!/usr/bin/env python3
"""Mac app: podcast audio, saved avatars, and a cartoon video."""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
import uuid
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from cast_library import SUPPORT, forget_cast, keep_cast, list_cast, load_cast, update_puppet
from draw_avatar import draw_avatar, draw_background, draw_mouths
from podcast_processor import process_audio, speakers_in
from podcast_video import PALETTE, preview_puppet, render_cartoon
from rhubarb_sync import build_cues
from stage import PRESETS, forget_set, keep_set, list_sets, load_set, paint_stage

SUPPORT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(SUPPORT / "hf"))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(SUPPORT / "hf" / "hub"))
os.environ.setdefault("XDG_CACHE_HOME", str(SUPPORT / "cache"))
CONFIG = SUPPORT / "config.json"


def load_config():
    if CONFIG.exists():
        try:
            return json.loads(CONFIG.read_text())
        except Exception:
            return {}
    return {}


def save_config(data):
    CONFIG.write_text(json.dumps(data))


BG = "#161616"
INK = "#f5f5f7"
FIELD = "#2a2a2a"
LINE = "#3f3f3f"


def apply_dark(root):
    root.configure(bg=BG)
    root.tk_setPalette(
        background=BG,
        foreground=INK,
        activeBackground=FIELD,
        activeForeground=INK,
        highlightBackground=BG,
        highlightColor=INK,
        selectBackground="#5c5346",
        selectForeground=INK,
        insertBackground=INK,
    )
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=INK, fieldbackground=FIELD, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, troughcolor="#3a3a3a")
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=INK)
    style.configure("TButton", background=FIELD, foreground=INK, padding=(10, 6), bordercolor=LINE)
    style.map("TButton", background=[("active", "#3a3a3c"), ("disabled", "#242424")], foreground=[("disabled", "#8e8e93"), ("active", INK)])
    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=FIELD, foreground=INK, padding=(14, 6))
    style.map("TNotebook.Tab", background=[("selected", "#3a3a3c")], foreground=[("selected", INK)])
    style.configure("TEntry", fieldbackground=FIELD, foreground=INK, insertcolor=INK)
    style.configure("TSpinbox", fieldbackground=FIELD, foreground=INK, background=FIELD, arrowcolor=INK)
    style.configure("TCombobox", fieldbackground=FIELD, foreground=INK, background=FIELD, arrowcolor=INK)
    style.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", INK)])
    style.configure("TRadiobutton", background=BG, foreground=INK)
    style.map("TRadiobutton", background=[("active", BG)], foreground=[("active", INK)])
    style.configure(
        "Gold.Horizontal.TProgressbar",
        troughcolor=FIELD,
        background="#d4b483",
        bordercolor=BG,
        lightcolor="#d4b483",
        darkcolor="#d4b483",
    )
    root.option_add("*Foreground", INK)
    root.option_add("*Background", BG)
    root.option_add("*insertBackground", INK)
    root.option_add("*selectBackground", "#5c5346")
    root.option_add("*selectForeground", INK)


class App:
    def __init__(self, root):
        self.root = root
        root.title("Podcast to Cartoon")
        root.geometry("980x820")
        apply_dark(root)
        self.audio = None
        self.result = None
        self.cast = []
        self.selected = None
        self.speaker_vars = {}
        self.sets = []
        self.preview_photo = None
        self.set_photo = None
        cfg = load_config()

        tk.Label(root, text="Podcast to Cartoon", font=("Helvetica", 20, "bold"), bg=BG, fg=INK).pack(pady=(12, 2))
        tk.Label(
            root,
            text="Place each puppet, design the set, then make the video.",
            bg=BG,
            fg=INK,
        ).pack()

        keys = tk.Frame(root, bg=BG)
        keys.pack(pady=8)
        tk.Label(keys, text="Hugging Face token", bg=BG, fg=INK).grid(row=0, column=0, sticky="w")
        self.hf = ttk.Entry(keys, width=42, show="*")
        self.hf.grid(row=0, column=1, padx=6)
        if cfg.get("hf"):
            self.hf.insert(0, cfg["hf"])
        tk.Label(keys, text="xAI key (drawing only)", bg=BG, fg=INK).grid(row=1, column=0, sticky="w")
        self.xai = ttk.Entry(keys, width=42, show="*")
        self.xai.grid(row=1, column=1, padx=6, pady=4)
        if cfg.get("xai"):
            self.xai.insert(0, cfg["xai"])
        ttk.Button(keys, text="Save keys", command=self.save_keys).grid(row=0, column=2, rowspan=2, padx=6)

        self.bar = ttk.Progressbar(root, style="Gold.Horizontal.TProgressbar", mode="determinate", maximum=100)
        self.bar.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
        self.status = tk.Label(root, text="Ready", bg=BG, fg=INK, anchor="w", font=("Helvetica", 14))
        self.status.pack(side="bottom", fill="x", padx=16, pady=(4, 2))

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=6)
        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="y")
        tk.Label(left, text="Saved cast", bg=BG, fg=INK, font=("Helvetica", 13, "bold")).pack(anchor="w")
        self.cast_list = tk.Listbox(left, width=28, height=12, bg=FIELD, fg=INK, selectbackground="#5c5346", selectforeground=INK, highlightbackground=BG, highlightcolor=LINE)
        self.cast_list.pack(pady=4)
        self.cast_list.bind("<<ListboxSelect>>", self.on_select)
        row = tk.Frame(left, bg=BG)
        row.pack()
        ttk.Button(row, text="Add headshot", command=self.add_headshot).pack(side="left", padx=2)
        ttk.Button(row, text="Remove", command=self.remove_selected).pack(side="left", padx=2)
        tk.Label(left, text="Name", bg=BG, fg=INK).pack(anchor="w", pady=(8, 0))
        self.name = ttk.Entry(left, width=28)
        self.name.pack()
        tk.Label(left, text="Note for the drawing", bg=BG, fg=INK).pack(anchor="w")
        self.note = ttk.Entry(left, width=28)
        self.note.pack()
        self.portrait = tk.Label(left, bg=FIELD)
        self.portrait.pack(pady=(8, 4))
        self.portrait_photo = None
        ttk.Button(left, text="Draw avatar", command=self.start_draw).pack(pady=4, fill="x")
        ttk.Button(left, text="Cut mouths", command=self.start_mouths).pack(fill="x")
        ttk.Button(left, text="Keep avatar", command=self.keep_selected).pack(pady=4, fill="x")

        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(16, 0))
        book = ttk.Notebook(right)
        self.book = book
        book.pack(fill="both", expand=True)
        episode = tk.Frame(book, bg=BG)
        puppet = tk.Frame(book, bg=BG)
        self.puppet_tab = puppet
        studio = tk.Frame(book, bg=BG)
        book.add(episode, text="Episode")
        book.add(puppet, text="Puppet")
        book.add(studio, text="Set")
        ttk.Button(episode, text="Choose audio", command=self.choose_audio).pack(anchor="w", padx=8, pady=(8, 0))
        self.audio_label = tk.Label(episode, text="No audio yet", bg=BG, fg=INK)
        self.audio_label.pack(anchor="w", padx=8)
        spins = tk.Frame(episode, bg=BG)
        spins.pack(anchor="w", padx=8, pady=4)
        tk.Label(spins, text="Min", bg=BG, fg=INK).pack(side="left")
        self.min_sp = ttk.Spinbox(spins, from_=2, to=8, width=4)
        self.min_sp.delete(0, "end")
        self.min_sp.insert(0, "4")
        self.min_sp.pack(side="left", padx=4)
        tk.Label(spins, text="Max", bg=BG, fg=INK).pack(side="left")
        self.max_sp = ttk.Spinbox(spins, from_=2, to=8, width=4)
        self.max_sp.delete(0, "end")
        self.max_sp.insert(0, "5")
        self.max_sp.pack(side="left", padx=4)
        self.go = ttk.Button(episode, text="1. Find speakers", command=self.start_process)
        self.go.pack(anchor="w", padx=8, pady=4)
        self.assign = tk.Frame(episode, bg=BG)
        self.assign.pack(anchor="w", fill="x", padx=8, pady=4)
        self.video_btn = ttk.Button(episode, text="2. Make cartoon video", command=self.start_video, state="disabled")
        self.video_btn.pack(anchor="w", padx=8, pady=4)
        self.log = scrolledtext.ScrolledText(episode, height=5, width=70, bg=FIELD, fg=INK, insertbackground=INK, selectbackground="#5c5346", highlightbackground=BG)
        self.log.pack(fill="both", expand=True, pady=6)
        self._build_puppet(puppet)
        self._build_set(studio)
        self.write("Kept avatars live in this Mac account and can be reused on the next episode.\n")
        if cfg.get("hf") or cfg.get("xai"):
            self.write("Saved keys loaded.\n")
        self.hf.bind("<FocusOut>", lambda _e: self.persist_keys())
        self.xai.bind("<FocusOut>", lambda _e: self.persist_keys())
        root.protocol("WM_DELETE_WINDOW", self.close_app)
        self.refresh_cast()
        self.refresh_sets()

    def write(self, text):
        self.log.insert("end", text)
        self.log.see("end")

    def persist_keys(self):
        cfg = load_config()
        cfg["hf"] = self.hf.get().strip()
        cfg["xai"] = self.xai.get().strip()
        save_config(cfg)

    def save_keys(self):
        self.persist_keys()
        self.write("Keys saved on this Mac. They will be filled in next time you open the app.\n")

    def show_busy(self, label):
        self.status.config(text=label)
        self.bar.stop()
        self.bar.config(mode="indeterminate", maximum=100)
        self.bar.start(12)

    def show_progress(self, fraction, label):
        self.bar.stop()
        self.bar.config(mode="determinate", maximum=100)
        self.bar["value"] = max(0, min(100, float(fraction) * 100))
        self.status.config(text=label)

    def show_done(self, label):
        self.bar.stop()
        self.bar.config(mode="determinate", maximum=100)
        self.bar["value"] = 100
        self.status.config(text=label)

    def close_app(self):
        self.persist_keys()
        self.root.destroy()

    def refresh_cast(self):
        self.cast = list_cast()
        self.cast_list.delete(0, "end")
        for item in self.cast:
            mark = "drawn" if item.get("has_avatar") else "photo"
            self.cast_list.insert("end", f"{item.get('name', 'Unnamed')} ({mark})")

    def current(self):
        if self.selected is None:
            return None
        try:
            return load_cast(self.selected)
        except FileNotFoundError:
            return None

    def on_select(self, _event):
        sel = self.cast_list.curselection()
        if not sel:
            return
        item = self.cast[sel[0]]
        self.selected = item["id"]
        loaded = load_cast(item["id"])
        self.name.delete(0, "end")
        self.name.insert(0, loaded.get("name") or "")
        self.note.delete(0, "end")
        self.note.insert(0, loaded.get("note") or "")
        self.mouth_x.set(float(loaded.get("mouthX") or 50))
        self.mouth_y.set(float(loaded.get("mouthY") or 64))
        self.mouth_s.set(float(loaded.get("mouthScale") or 22))
        self.puppet_scale.set(int(float(loaded.get("puppetScale") or 1) * 100))
        self._show_portrait()
        self.refresh_puppet_preview()

    def add_headshot(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
        if not path:
            return
        avatar_id = uuid.uuid4().hex
        photo = Path(path).read_bytes()
        name = Path(path).stem.replace("-", " ").replace("_", " ")
        keep_cast(avatar_id, name, "", photo, None, 50, 64, 22)
        self.refresh_cast()
        self.selected = avatar_id
        self._show_portrait()
        self.write(f"Saved headshot {name}. Draw an avatar when you are ready.\n")

    def keep_selected(self):
        loaded = self.current()
        if not loaded:
            messagebox.showwarning("No one selected", "Add a headshot first.")
            return
        photo = Path(loaded["photo"]).read_bytes() if Path(loaded["photo"]).exists() else b""
        avatar = Path(loaded["avatar"]).read_bytes() if loaded.get("avatar") else None
        mouths = {}
        for key, path in (loaded.get("mouths") or {}).items():
            mouths[key] = Path(path).read_bytes()
        keep_cast(
            loaded["id"],
            self.name.get().strip() or loaded.get("name") or "Unnamed",
            self.note.get().strip(),
            photo,
            avatar,
            float(loaded.get("mouthX") or 50),
            float(loaded.get("mouthY") or 64),
            float(loaded.get("mouthScale") or 22),
            mouths or None,
        )
        self.refresh_cast()
        self.write("Avatar kept. It will be here next time you open the app.\n")

    def remove_selected(self):
        if not self.selected:
            return
        forget_cast(self.selected)
        self.selected = None
        self.refresh_cast()

    def start_draw(self):
        loaded = self.current()
        if not loaded:
            messagebox.showwarning("No headshot", "Add a headshot first.")
            return
        self.persist_keys()
        key = self.xai.get().strip()
        if not key:
            messagebox.showwarning("Missing key", "Paste an xAI key and click Save keys.")
            return
        job = {
            "id": loaded["id"],
            "photo": loaded["photo"],
            "name": self.name.get().strip() or loaded.get("name") or "Unnamed",
            "note": self.note.get().strip(),
            "key": key,
            "mouthX": float(loaded.get("mouthX") or 50),
            "mouthY": float(loaded.get("mouthY") or 64),
            "mouthScale": float(loaded.get("mouthScale") or 22),
        }
        self.show_busy("Drawing the avatar")
        threading.Thread(target=self._draw, args=(job,), daemon=True).start()

    def _draw(self, job):
        try:
            blob = draw_avatar(job["photo"], job["key"], job["note"])
            keep_cast(
                job["id"],
                job["name"],
                job["note"],
                Path(job["photo"]).read_bytes(),
                blob,
                job["mouthX"],
                job["mouthY"],
                job["mouthScale"],
                None,
            )
            self.root.after(0, self._drew)
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._fail(e))

    def _drew(self):
        self.refresh_cast()
        self._show_portrait()
        self.book.select(self.puppet_tab)
        self.refresh_puppet_preview()
        self.show_done("Avatar drawn")
        self.write("Avatar drawn and kept.\n")

    def _show_portrait(self):
        from PIL import Image, ImageTk

        loaded = self.current()
        path = (loaded or {}).get("avatar") or (loaded or {}).get("photo")
        if not path or not Path(path).exists():
            self.portrait.configure(image="")
            self.portrait_photo = None
            return
        picture = Image.open(path).convert("RGBA")
        picture.thumbnail((220, 260))
        self.portrait_photo = ImageTk.PhotoImage(picture)
        self.portrait.configure(image=self.portrait_photo)

    def start_mouths(self):
        loaded = self.current()
        if not loaded or not loaded.get("avatar"):
            messagebox.showwarning("No avatar", "Draw the avatar before cutting mouths.")
            return
        self.persist_keys()
        key = self.xai.get().strip()
        if not key:
            messagebox.showwarning("Missing key", "Paste an xAI key and click Save keys.")
            return
        job = {
            "id": loaded["id"],
            "photo": loaded["photo"],
            "avatar": loaded["avatar"],
            "name": self.name.get().strip() or loaded.get("name") or "Unnamed",
            "note": self.note.get().strip(),
            "key": key,
            "mouthX": float(loaded.get("mouthX") or 50),
            "mouthY": float(loaded.get("mouthY") or 64),
            "mouthScale": float(loaded.get("mouthScale") or 22),
        }
        self.show_busy("Cutting the mouths")
        threading.Thread(target=self._mouths, args=(job,), daemon=True).start()

    def _mouths(self, job):
        try:
            mouths = draw_mouths(job["avatar"], job["key"])
            keep_cast(
                job["id"],
                job["name"],
                job["note"],
                Path(job["photo"]).read_bytes(),
                Path(job["avatar"]).read_bytes(),
                job["mouthX"],
                job["mouthY"],
                job["mouthScale"],
                mouths,
            )
            self.root.after(0, lambda: self.show_done("Mouths ready"))
            self.root.after(0, lambda: self.write("Mouths cut and kept with this avatar.\n"))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._fail(e))

    def choose_audio(self):
        path = filedialog.askopenfilename(filetypes=[("Audio", "*.mp3 *.wav *.m4a *.mp4")])
        if path:
            self.audio = path
            self.audio_label.config(text=Path(path).name, font=("Helvetica", 16, "bold"))
            self.show_done("Audio ready")

    def start_process(self):
        if not self.audio:
            messagebox.showwarning("Missing audio", "Choose an audio file first.")
            return
        token = self.hf.get().strip()
        if not token:
            messagebox.showwarning("Missing token", "Paste your Hugging Face token.")
            return
        self.persist_keys()
        os.environ["HF_TOKEN"] = token
        self.go.config(state="disabled")
        self.video_btn.config(state="disabled")
        self.show_busy("Finding speakers")
        audio = self.audio
        low = int(self.min_sp.get())
        high = int(self.max_sp.get())
        threading.Thread(target=self._process, args=(audio, low, high), daemon=True).start()

    def _process(self, audio, low, high):
        try:
            out = Path.home() / "Desktop" / "Podcast Processor"
            def report(amount, label):
                self.root.after(0, lambda a=amount, s=label: self.show_progress(a, s))

            result = process_audio(
                audio,
                str(out),
                model="small",
                min_speakers=low,
                max_speakers=high,
                progress=report,
            )
            self.root.after(0, lambda: self._processed(result, out))
        except Exception as exc:
            self.root.after(0, lambda: self._fail(exc))

    def _processed(self, result, out):
        self.result = result
        self.go.config(state="normal")
        self.video_btn.config(state="normal")
        names = speakers_in(result)
        self.show_done(f"{len(names)} speakers found")
        self.write("Speakers: " + ", ".join(names or ["none"]) + "\n")
        for child in self.assign.winfo_children():
            child.destroy()
        self.speaker_vars = {}
        choices = ["(simple card)"] + [item.get("name") or item["id"] for item in self.cast]
        for i, sp in enumerate(names):
            ink, fill = PALETTE[i % len(PALETTE)]
            tk.Label(self.assign, text=f"  {i + 1}  ", bg=ink, fg=INK, font=("Helvetica", 13, "bold")).grid(row=i, column=0, padx=(0, 8), pady=3)
            tk.Label(self.assign, text=sp, bg=fill, fg="#1f2a24", padx=8).grid(row=i, column=1, sticky="ew", pady=3)
            var = tk.StringVar(value=choices[min(i + 1, len(choices) - 1)] if len(choices) > 1 else choices[0])
            self.speaker_vars[sp] = var
            ttk.Combobox(self.assign, textvariable=var, values=choices, width=24, state="readonly").grid(row=i, column=2, padx=8)

    def _cast_for_speakers(self):
        by_name = {item.get("name"): item["id"] for item in self.cast}
        assigned = {}
        for sp, var in self.speaker_vars.items():
            picked = var.get()
            if picked in by_name:
                assigned[sp] = load_cast(by_name[picked])
        return assigned

    def start_video(self):
        if not self.result:
            return
        self.video_btn.config(state="disabled")
        self.show_busy("Matching mouths")
        names = {}
        for sp, var in self.speaker_vars.items():
            picked = var.get()
            names[sp] = picked if picked != "(simple card)" else sp
        threading.Thread(
            target=self._video,
            args=(self.audio, self.result, names, self._cast_for_speakers()),
            daemon=True,
        ).start()

    def _video(self, audio, result, names, cast):
        try:
            out = Path.home() / "Desktop" / "Podcast Processor"
            out.mkdir(parents=True, exist_ok=True)
            dest = out / f"{Path(audio).stem}_cartoon.mp4"
            def report(amount, label):
                self.root.after(0, lambda a=amount, s=label: self.show_progress(a * 0.35, s))

            try:
                cues = build_cues(audio, result, report)
            except Exception as exc:
                cues = None
                self.root.after(0, lambda e=exc: self.write(f"Lip sync fell back to a timer: {e}\n"))
            def progress(done, total):
                self.root.after(0, lambda d=done, n=total: self.show_progress(0.35 + 0.65 * d / n, f"Drawing the cartoon   {d} / {n}"))

            background = self._background_for_video()
            render_cartoon(result, audio, dest, names, cast, progress, cues, background)
            self.root.after(0, lambda: self._video_done(dest))
        except Exception as exc:
            self.root.after(0, lambda: self._fail(exc))


    def _build_puppet(self, parent):
        tk.Label(parent, text="Move the mouth, then set how big this person stands.", bg=BG, fg=INK).pack(anchor="w", padx=8, pady=(8, 0))
        self.preview = tk.Label(parent, bg=BG, fg=INK)
        self.preview.pack(anchor="w", padx=8, pady=4)
        self.mouth_shape = tk.StringVar(value="closed")
        shapes = tk.Frame(parent, bg=BG)
        shapes.pack(anchor="w", padx=8)
        for name in ("closed", "small", "medium", "wide", "round", "teeth"):
            ttk.Radiobutton(
                shapes, text=name, value=name, variable=self.mouth_shape,
                command=self.refresh_puppet_preview,
            ).pack(side="left")
        self.puppet_scale = tk.Scale(parent, label="Puppet size", from_=60, to=160, orient="horizontal", bg=BG, fg=INK, troughcolor=FIELD, highlightbackground=BG, activebackground=BG, command=lambda _v: self.refresh_puppet_preview())
        self.puppet_scale.set(100)
        self.puppet_scale.pack(fill="x", padx=8)
        self.mouth_x = tk.Scale(parent, label="Mouth sideways", from_=30, to=70, orient="horizontal", bg=BG, fg=INK, troughcolor=FIELD, highlightbackground=BG, activebackground=BG, command=lambda _v: self.refresh_puppet_preview())
        self.mouth_x.set(50)
        self.mouth_x.pack(fill="x", padx=8)
        self.mouth_y = tk.Scale(parent, label="Mouth height", from_=48, to=80, orient="horizontal", bg=BG, fg=INK, troughcolor=FIELD, highlightbackground=BG, activebackground=BG, command=lambda _v: self.refresh_puppet_preview())
        self.mouth_y.set(64)
        self.mouth_y.pack(fill="x", padx=8)
        self.mouth_s = tk.Scale(parent, label="Mouth size", from_=10, to=40, orient="horizontal", bg=BG, fg=INK, troughcolor=FIELD, highlightbackground=BG, activebackground=BG, command=lambda _v: self.refresh_puppet_preview())
        self.mouth_s.set(22)
        self.mouth_s.pack(fill="x", padx=8)
        ttk.Button(parent, text="Save puppet", command=self.save_puppet).pack(anchor="w", padx=8, pady=6)

    def refresh_puppet_preview(self):
        from PIL import ImageTk

        loaded = self.current() or {}
        sample = {
            "name": self.name.get().strip() if loaded else "",
            "avatar": loaded.get("avatar"),
            "photo": loaded.get("photo"),
            "mouths": loaded.get("mouths") or {},
            "mouthX": self.mouth_x.get(),
            "mouthY": self.mouth_y.get(),
            "mouthScale": self.mouth_s.get(),
        }
        card = preview_puppet(sample, self.mouth_shape.get())
        self.preview_photo = ImageTk.PhotoImage(card.convert("RGBA"))
        self.preview.configure(image=self.preview_photo)

    def save_puppet(self):
        if not self.selected:
            messagebox.showwarning("No one selected", "Add a headshot first.")
            return
        update_puppet(
            self.selected,
            float(self.mouth_x.get()),
            float(self.mouth_y.get()),
            float(self.mouth_s.get()),
            float(self.puppet_scale.get()) / 100,
        )
        self.write("Puppet saved. The next video uses this mouth and size.\n")

    def _build_set(self, parent):
        tk.Label(parent, text="Pick a room, or describe one and draw it.", bg=BG, fg=INK).pack(anchor="w", padx=8, pady=(8, 0))
        self.set_preview = tk.Label(parent, bg=BG, fg=INK)
        self.set_preview.pack(anchor="w", padx=8, pady=4)
        row = tk.Frame(parent, bg=BG)
        row.pack(anchor="w", padx=8)
        tk.Label(row, text="Look", bg=BG, fg=INK).pack(side="left")
        self.set_preset = ttk.Combobox(row, values=PRESETS, width=16, state="readonly")
        self.set_preset.set("studio")
        self.set_preset.pack(side="left", padx=6)
        self.set_preset.bind("<<ComboboxSelected>>", lambda _e: self.refresh_set_preview())
        tk.Label(parent, text="Name", bg=BG, fg=INK).pack(anchor="w", padx=8)
        self.set_name = ttk.Entry(parent, width=28)
        self.set_name.pack(anchor="w", padx=8)
        tk.Label(parent, text="Describe a drawn set", bg=BG, fg=INK).pack(anchor="w", padx=8)
        self.set_note = ttk.Entry(parent, width=42)
        self.set_note.pack(anchor="w", padx=8, pady=2)
        buttons = tk.Frame(parent, bg=BG)
        buttons.pack(anchor="w", padx=8, pady=4)
        ttk.Button(buttons, text="Save this look", command=self.save_set).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Draw this set", command=self.start_draw_set).pack(side="left")
        self.set_list = tk.Listbox(parent, height=4, bg=FIELD, fg=INK, selectbackground="#5c5346", selectforeground=INK, highlightbackground=BG)
        self.set_list.pack(fill="x", padx=8, pady=4)
        self.set_list.bind("<<ListboxSelect>>", self.on_set_select)
        actions = tk.Frame(parent, bg=BG)
        actions.pack(anchor="w", padx=8)
        ttk.Button(actions, text="Use this set", command=self.use_selected_set).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Remove set", command=self.remove_set).pack(side="left")
        self.refresh_set_preview()

    def refresh_set_preview(self):
        from PIL import ImageTk

        plate = paint_stage({"preset": self.set_preset.get()}, (320, 180))
        self.set_photo = ImageTk.PhotoImage(plate)
        self.set_preview.configure(image=self.set_photo)

    def refresh_sets(self):
        self.sets = list_sets()
        self.set_list.delete(0, "end")
        chosen = load_config().get("backgroundId")
        for item in self.sets:
            mark = "in use" if item["id"] == chosen else item.get("preset") or "set"
            self.set_list.insert("end", f"{item.get('name', 'Set')} ({mark})")

    def save_set(self):
        preset = self.set_preset.get() or "paper"
        set_id = uuid.uuid4().hex
        keep_set(set_id, self.set_name.get().strip() or preset, preset)
        self._remember_set(set_id)
        self.refresh_sets()
        self.write(f"Saved the {preset} set.\n")

    def start_draw_set(self):
        self.persist_keys()
        note = self.set_note.get().strip()
        if not note:
            messagebox.showwarning("Add a description", "Describe the room you want drawn.")
            return
        key = self.xai.get().strip()
        if not key:
            messagebox.showwarning("Missing key", "Paste an xAI key and click Save keys.")
            return
        name = self.set_name.get().strip()
        preset = self.set_preset.get() or "paper"
        self.show_busy("Drawing the set")
        threading.Thread(target=self._draw_set, args=(note, key, name, preset), daemon=True).start()

    def _draw_set(self, note, key, name, preset):
        try:
            blob = draw_background(note, key)
            set_id = uuid.uuid4().hex
            keep_set(set_id, name or "Drawn set", preset, blob)
            self.root.after(0, lambda: self._set_drawn(set_id))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._fail(e))

    def _set_drawn(self, set_id):
        self._remember_set(set_id)
        self.refresh_sets()
        self._show_set(load_set(set_id))
        self.show_done("Set ready")
        self.write("Set drawn and saved. The next video uses it.\n")

    def on_set_select(self, _event):
        sel = self.set_list.curselection()
        if not sel:
            return
        self._show_set(self.sets[sel[0]])

    def _show_set(self, item):
        from PIL import ImageTk

        plate = paint_stage(item, (320, 180))
        self.set_photo = ImageTk.PhotoImage(plate)
        self.set_preview.configure(image=self.set_photo)

    def use_selected_set(self):
        sel = self.set_list.curselection()
        if not sel:
            messagebox.showwarning("No set", "Save a look first.")
            return
        self._remember_set(self.sets[sel[0]]["id"])
        self.refresh_sets()
        self.write("This set will be the video background.\n")

    def remove_set(self):
        sel = self.set_list.curselection()
        if not sel:
            return
        set_id = self.sets[sel[0]]["id"]
        forget_set(set_id)
        cfg = load_config()
        if cfg.get("backgroundId") == set_id:
            cfg["backgroundId"] = ""
            save_config(cfg)
        self.refresh_sets()
        self.refresh_set_preview()

    def _remember_set(self, set_id):
        cfg = load_config()
        cfg["backgroundId"] = set_id
        cfg["hf"] = self.hf.get().strip()
        cfg["xai"] = self.xai.get().strip()
        save_config(cfg)

    def _background_for_video(self):
        set_id = load_config().get("backgroundId")
        if not set_id:
            return {"preset": "paper"}
        try:
            return load_set(set_id)
        except FileNotFoundError:
            return {"preset": "paper"}

    def _video_done(self, dest):
        self.video_btn.config(state="normal")
        self.show_done("Video saved")
        self.write(f"Video saved: {dest}\n")
        messagebox.showinfo("Video ready", f"Saved to\n{dest}")

    def _fail(self, exc):
        self.go.config(state="normal")
        self.video_btn.config(state="normal")
        self.bar.stop()
        self.bar.config(mode="determinate")
        self.bar["value"] = 0
        self.status.config(text="Something went wrong")
        self.write(f"\nError: {exc}\n")
        messagebox.showerror("Something went wrong", str(exc))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
