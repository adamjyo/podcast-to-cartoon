#!/usr/bin/env python3
"""Mac app: podcast audio, saved avatars, and a cartoon video."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
import uuid
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

import certifi

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["CURL_CA_BUNDLE"] = certifi.where()

from cast_library import SUPPORT, forget_cast, install_included, keep_cast, list_cast, load_cast, update_placement, update_puppet
from draw_avatar import draw_avatar, draw_background, draw_mouths, parse_mouth_sheet
from podcast_processor import process_audio, process_tracks, speakers_in
from podcast_video import PALETTE, preview_puppet, render_cartoon
from rhubarb_sync import build_cues, mouth_at
from opentoonz_export import export_opentoonz, export_parts, launch_opentoonz
from stage import PRESETS, bundled_background, forget_set, keep_set, list_sets, load_set, paint_stage

SUPPORT.mkdir(parents=True, exist_ok=True)
install_included()
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


def _clock(seconds):
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


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
        thickness=22,
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
        root.geometry("1040x1040")
        apply_dark(root)
        self.audio = None
        self.tracks = []
        self.parts = []
        self.scene_index = 0
        self.drag = None
        self.scene_w = 960
        self.scene_h = 540
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.playhead = 0.0
        self._play_offset = 0.0
        self._play_duration = 60.0
        self.view_start = 0.0
        self.cuts = [{"t": 0.0, "shot": "wide"}]
        self.program = "wide"
        self.follow_switch = True
        self.view_span = 60.0
        self.camera_keys = [{"t": 0.0, "zoom": 1.0, "pan_x": 0.0, "pan_y": 0.0}]
        self.selection = None
        self.cropping = False
        self._crop_rect = None
        self._play_started = None
        self._play_cues = {}
        self._play_token = 0
        self._player = None
        self.bg_image = ""
        self.bg = {"x": 0.0, "y": 0.0, "h": 1.0}
        self.fg = {"path": "", "x": 0.0, "y": 0.58, "h": 0.42}
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
            text="Drag a person to move them. Drag a corner to resize. Drag a mouth to place it, and its corner to resize it. Then press Play.",
            bg=BG,
            fg=INK,
        ).pack()

        self.bar = ttk.Progressbar(root, style="Gold.Horizontal.TProgressbar", mode="determinate", maximum=100)
        self.bar.pack(side="bottom", fill="x", padx=16, pady=(0, 8), ipady=6)
        self.percent = tk.Label(root, text="0%", bg=BG, fg=INK, font=("Helvetica", 22, "bold"))
        self.percent.pack(side="bottom", anchor="w", padx=16)
        self.status = tk.Label(root, text="Ready", bg=BG, fg=INK, anchor="w", font=("Helvetica", 14))
        self.status.pack(side="bottom", fill="x", padx=16, pady=(8, 0))
        self._job_started = None
        self._job_label = "Ready"
        self._job_fraction = 0
        self._pulse_on = False
        self._same_since = None

        book = ttk.Notebook(root)
        self.book = book
        book.pack(fill="both", expand=True, padx=12, pady=6)
        episode = tk.Frame(book, bg=BG)
        more = tk.Frame(book, bg=BG)
        puppet = tk.Frame(more, bg=BG)
        self.puppet_tab = puppet
        studio = tk.Frame(more, bg=BG)
        book.add(episode, text="Episode")
        book.add(more, text="More")

        tk.Label(
            episode,
            text="Uncheck On to leave a person out of this video.",
            bg=BG,
            fg=INK,
        ).pack(anchor="w", padx=8, pady=(10, 0))
        self.scene = tk.Canvas(episode, width=self.scene_w, height=self.scene_h, bg="#1c2420", highlightthickness=0)
        self.scene.pack(anchor="w", padx=8, pady=(8, 0))
        switch = tk.Frame(episode, bg=BG)
        switch.pack(anchor="w", fill="x", padx=8, pady=(6, 0))
        self.on_air = tk.Label(
            switch, text="ON AIR   Wide", bg="#c45c26", fg="#fffaf3",
            font=("Helvetica", 13, "bold"), padx=12, pady=6,
        )
        self.on_air.pack(side="left")
        self.switch_box = tk.Frame(switch, bg=BG)
        self.switch_box.pack(side="left", padx=8)
        ttk.Button(switch, text="Export switched MP4", command=self.export_switched).pack(side="right")
        tk.Label(
            episode,
            text="Wide is the whole table. Each name is a close-up. Click one while it plays to cut, like a live show. Export writes that cut list into an MP4.",
            bg=BG, fg=INK,
        ).pack(anchor="w", padx=8, pady=(4, 0))
        self.scene.bind("<Button-1>", self.scene_down)
        self.scene.bind("<B1-Motion>", self.scene_drag)
        self.scene.bind("<ButtonRelease-1>", self.scene_up)
        self.scene.bind("<Shift-Button-1>", self.scene_pan_down)
        self.scene.bind("<Shift-B1-Motion>", self.scene_pan_drag)
        self.scene.bind("<Double-Button-1>", self.scene_open_person)
        self.scene.bind("<MouseWheel>", self.scene_wheel)
        self.scene.bind("<Button-4>", self.scene_wheel)
        self.scene.bind("<Button-5>", self.scene_wheel)
        self.scene.bind("<Button-3>", self.scene_pan_down)
        self.scene.bind("<B3-Motion>", self.scene_pan_drag)
        self.scene.bind("<Button-2>", self.scene_pan_down)
        self.scene.bind("<B2-Motion>", self.scene_pan_drag)
        self.track = tk.Canvas(episode, width=self.scene_w, height=64, bg="#141a17", highlightthickness=0)
        self.track.pack(anchor="w", padx=8, pady=(4, 0))
        self.track.bind("<Button-1>", self.track_down)
        self.track.bind("<B1-Motion>", self.track_drag)
        group_tools = tk.Frame(episode, bg=BG)
        group_tools.pack(anchor="w", padx=8, pady=8)
        ttk.Button(group_tools, text="Background", command=self.open_background).pack(side="left")
        ttk.Button(group_tools, text="Foreground", command=self.open_foreground).pack(side="left", padx=6)
        self.part_bg = ttk.Combobox(group_tools, values=("coffee shop", "library"), width=14, state="readonly")
        self.part_bg.set("coffee shop")
        self.part_bg.pack(side="left", padx=6)
        self.part_bg.bind("<<ComboboxSelected>>", lambda _e: self.draw_scene())
        self.play_btn = ttk.Button(group_tools, text="Play", command=self.play_episode)
        self.play_btn.pack(side="left", padx=8)
        ttk.Button(group_tools, text="Stop", command=self.stop_play).pack(side="left")
        self.pan_btn = ttk.Button(group_tools, text="Pan camera", command=self.toggle_pan)
        self.pan_btn.pack(side="left", padx=(12, 0))
        ttk.Button(group_tools, text="Camera in", command=lambda: self.zoom_by(1.25)).pack(side="left", padx=4)
        ttk.Button(group_tools, text="Camera out", command=lambda: self.zoom_by(0.8)).pack(side="left", padx=4)
        ttk.Button(group_tools, text="Full scene", command=self.zoom_fit).pack(side="left")
        self.crop_btn = ttk.Button(group_tools, text="Crop", command=self.toggle_crop)
        self.crop_btn.pack(side="left", padx=(8, 0))
        self.parts_box = tk.Frame(episode, bg=BG)
        self.parts_box.pack(anchor="w", fill="x", padx=8)
        self.log = scrolledtext.ScrolledText(episode, height=4, width=70, bg=FIELD, fg=INK, insertbackground=INK, selectbackground="#5c5346", highlightbackground=BG)
        self.log.pack(fill="both", expand=True, padx=8, pady=6)

        keys = tk.Frame(more, bg=BG)
        keys.pack(anchor="w", padx=8, pady=8)
        tk.Label(keys, text="Hugging Face token", bg=BG, fg=INK).grid(row=0, column=0, sticky="w")
        self.hf = ttk.Entry(keys, width=42, show="*")
        self.hf.grid(row=0, column=1, padx=6)
        if cfg.get("hf"):
            self.hf.insert(0, cfg["hf"])
        tk.Label(keys, text="xAI key, only for drawing", bg=BG, fg=INK).grid(row=1, column=0, sticky="w")
        self.xai = ttk.Entry(keys, width=42, show="*")
        self.xai.grid(row=1, column=1, padx=6, pady=4)
        if cfg.get("xai"):
            self.xai.insert(0, cfg["xai"])
        ttk.Button(keys, text="Save keys", command=self.save_keys).grid(row=0, column=2, rowspan=2, padx=6)

        old = tk.Frame(more, bg=BG)
        old.pack(anchor="w", padx=8, pady=4)
        ttk.Button(old, text="Choose one mixed recording", command=self.choose_audio).pack(side="left")
        self.audio_label = tk.Label(old, text="No mixed recording", bg=BG, fg=INK)
        self.audio_label.pack(side="left", padx=8)
        spins = tk.Frame(more, bg=BG)
        spins.pack(anchor="w", padx=8, pady=4)
        tk.Label(spins, text="Speakers from", bg=BG, fg=INK).pack(side="left")
        self.min_sp = ttk.Spinbox(spins, from_=2, to=8, width=4)
        self.min_sp.delete(0, "end")
        self.min_sp.insert(0, "4")
        self.min_sp.pack(side="left", padx=4)
        tk.Label(spins, text="to", bg=BG, fg=INK).pack(side="left")
        self.max_sp = ttk.Spinbox(spins, from_=2, to=8, width=4)
        self.max_sp.delete(0, "end")
        self.max_sp.insert(0, "5")
        self.max_sp.pack(side="left", padx=4)
        self.go = ttk.Button(spins, text="Find speakers in the mix", command=self.start_process)
        self.go.pack(side="left", padx=8)
        self.assign = tk.Frame(more, bg=BG)
        self.assign.pack(anchor="w", fill="x", padx=8, pady=4)
        actions = tk.Frame(more, bg=BG)
        actions.pack(anchor="w", padx=8)
        self.video_btn = ttk.Button(actions, text="Save a movie", command=self.start_video, state="disabled")
        self.video_btn.pack(side="left", padx=(0, 6))
        self.toonz_btn = ttk.Button(actions, text="Open in OpenToonz", command=self.start_opentoonz, state="disabled")

        left = tk.Frame(more, bg=BG)
        left.pack(anchor="w", padx=8, pady=8)
        tk.Label(left, text="Saved cast", bg=BG, fg=INK, font=("Helvetica", 13, "bold")).pack(anchor="w")
        self.cast_list = tk.Listbox(left, width=28, height=6, bg=FIELD, fg=INK, selectbackground="#5c5346", selectforeground=INK, highlightbackground=BG, highlightcolor=LINE)
        self.cast_list.pack(pady=4, anchor="w")
        self.cast_list.bind("<<ListboxSelect>>", self.on_select)
        row = tk.Frame(left, bg=BG)
        row.pack(anchor="w")
        ttk.Button(row, text="Add headshot", command=self.add_headshot).pack(side="left", padx=2)
        ttk.Button(row, text="Remove", command=self.remove_selected).pack(side="left", padx=2)
        tk.Label(left, text="Name", bg=BG, fg=INK).pack(anchor="w", pady=(8, 0))
        self.name = ttk.Entry(left, width=28)
        self.name.pack(anchor="w")
        tk.Label(left, text="Note for the drawing", bg=BG, fg=INK).pack(anchor="w")
        self.note = ttk.Entry(left, width=28)
        self.note.pack(anchor="w")
        self.portrait = tk.Label(left, bg=FIELD)
        self.portrait.pack(pady=(8, 4), anchor="w")
        self.portrait_photo = None
        draw_row = tk.Frame(left, bg=BG)
        draw_row.pack(anchor="w")
        ttk.Button(draw_row, text="Draw avatar", command=self.start_draw).pack(side="left", padx=2)
        ttk.Button(draw_row, text="Cut mouths", command=self.start_mouths).pack(side="left", padx=2)
        ttk.Button(draw_row, text="Keep avatar", command=self.keep_selected).pack(side="left", padx=2)
        self._build_puppet(puppet)
        self._build_set(studio)
        puppet.pack(anchor="w", fill="x")
        studio.pack(anchor="w", fill="x")
        for name in ("Adam", "Ben", "Corey", "Emily", "Abby R", "Abby S"):
            self.add_part(name)
        self.write("Fill the rows you need. Empty rows are skipped.\n")
        if cfg.get("hf") or cfg.get("xai"):
            self.write("Saved keys loaded. They are under More.\n")
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
        self._job_started = time.time()
        self._job_label = label
        self._job_fraction = None
        self._same_since = time.time()
        self._ensure_pulse()
        self._paint_progress()

    def show_progress(self, fraction, label):
        if self._job_started is None:
            self._job_started = time.time()
        if label != self._job_label or abs((fraction or 0) - (self._job_fraction or 0)) > 0.005:
            self._same_since = time.time()
        self._job_label = label
        self._job_fraction = fraction
        self._ensure_pulse()
        self._paint_progress()

    def _ensure_pulse(self):
        if self._pulse_on:
            return
        self._pulse_on = True
        self.root.after(1000, self._pulse)

    def _pulse(self):
        if self._job_started is None:
            self._pulse_on = False
            return
        self._paint_progress()
        self.root.after(1000, self._pulse)

    def _paint_progress(self):
        elapsed = max(0, time.time() - (self._job_started or time.time()))
        stalled = self._same_since is not None and time.time() - self._same_since > 20
        if self._job_fraction is None:
            if self.bar.cget("mode") != "indeterminate":
                self.bar.stop()
                self.bar.config(mode="indeterminate", maximum=100)
                self.bar.start(12)
            self.percent.config(text="…")
            note = "Still working." if stalled else ""
            self.status.config(text=f"{self._job_label}   {_clock(elapsed)} gone {note}".strip())
            return
        pct = max(0, min(100, float(self._job_fraction) * 100))
        if pct >= 8:
            remain = elapsed * (100 - pct) / pct
            timing = f"{_clock(elapsed)} gone, about {_clock(remain)} left"
        else:
            timing = f"{_clock(elapsed)} gone"
        if stalled and pct < 15:
            timing += ". Still on the speech model. Quit and reopen if this stays here"
        self.bar.stop()
        self.bar.config(mode="determinate", maximum=100)
        self.bar["value"] = pct
        self.percent.config(text=f"{pct:.0f}%")
        self.status.config(text=f"{self._job_label}   {timing}")

    def show_done(self, label):
        self._job_started = None
        self._pulse_on = False
        self.bar.stop()
        self.bar.config(mode="determinate", maximum=100)
        self.bar["value"] = 100
        self.percent.config(text="100%")
        self.status.config(text=label)

    def close_app(self):
        self.stop_play()
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

    def add_part(self, name=None):
        if len(self.parts) >= 6:
            messagebox.showinfo("Six people", "A group already has six people.")
            return
        label = name or f"Person {len(self.parts) + 1}"
        person = ""
        mouths = {}
        mouth_x, mouth_y, mouth_s = 50.0, 42.0, 18.0
        cast_id = ""
        scene_x = scene_y = scene_h = None
        matches = [item for item in (self.cast or list_cast()) if (item.get("name") or "") == label]
        matches.sort(key=lambda item: (0 if str(item.get("id", "")).startswith("included-") else 1, -(item.get("savedAt") or 0)))
        if matches:
            loaded = load_cast(matches[0]["id"])
            cast_id = loaded.get("id") or ""
            person = loaded.get("avatar") or ""
            mouths = dict(loaded.get("mouths") or {})
            mouth_x = float(loaded.get("mouthX") or 50)
            mouth_y = float(loaded.get("mouthY") or 42)
            mouth_s = float(loaded.get("mouthScale") or 18)
            scene_x = loaded.get("sceneX")
            scene_y = loaded.get("sceneY")
            scene_h = loaded.get("sceneH")
        index = len(self.parts)
        self.parts.append({
            "name": tk.StringVar(value=label),
            "audio": "",
            "person": person,
            "mouths": mouths,
            "cast_id": cast_id,
            "x": float(scene_x) if scene_x is not None else 0.03 + index * 0.155,
            "y": float(scene_y) if scene_y is not None else 0.08,
            "h": float(scene_h) if scene_h is not None else 0.78,
            "mouthX": mouth_x,
            "mouthY": mouth_y,
            "mouthScale": mouth_s,
            "on": tk.BooleanVar(value=True),
        })
        self.refresh_parts()

    def _screen_box(self, x, y, w, h):
        z = self.zoom
        return (
            int((x - self.pan_x) * z),
            int((y - self.pan_y) * z),
            max(1, int(w * z)),
            max(1, int(h * z)),
        )

    def zoom_by(self, factor):
        self.follow_switch = False
        self._zoom_at(self.scene_w / 2, self.scene_h / 2, self.zoom * factor)

    def zoom_fit(self):
        self.follow_switch = False
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.remember_camera()
        self.draw_scene()

    def _zoom_at(self, sx, sy, new_zoom):
        new_zoom = max(0.4, min(6.0, new_zoom))
        world_x = sx / self.zoom + self.pan_x
        world_y = sy / self.zoom + self.pan_y
        self.zoom = new_zoom
        self.pan_x = world_x - sx / self.zoom
        self.pan_y = world_y - sy / self.zoom
        self.remember_camera()
        self.draw_scene()

    def remember_camera(self):
        shot = {
            "t": round(float(self.playhead), 2),
            "zoom": float(self.zoom),
            "pan_x": float(self.pan_x),
            "pan_y": float(self.pan_y),
        }
        for key in self.camera_keys:
            if abs(key["t"] - shot["t"]) < 0.08:
                key.update(shot)
                return
        self.camera_keys.append(shot)
        self.camera_keys.sort(key=lambda item: item["t"])

    def apply_camera(self):
        keys = sorted(self.camera_keys, key=lambda item: item["t"])
        if not keys:
            return
        t = float(self.playhead)
        if t <= keys[0]["t"]:
            left = right = keys[0]
            blend = 0
        elif t >= keys[-1]["t"]:
            left = right = keys[-1]
            blend = 0
        else:
            left, right = keys[0], keys[-1]
            for earlier, later in zip(keys, keys[1:]):
                if earlier["t"] <= t <= later["t"]:
                    left, right = earlier, later
                    break
            blend = (t - left["t"]) / max(0.001, right["t"] - left["t"])
        self.zoom = left["zoom"] + (right["zoom"] - left["zoom"]) * blend
        self.pan_x = left["pan_x"] + (right["pan_x"] - left["pan_x"]) * blend
        self.pan_y = left["pan_y"] + (right["pan_y"] - left["pan_y"]) * blend

    def scene_wheel(self, event):
        if getattr(event, "num", None) == 5 or getattr(event, "delta", 0) < 0:
            factor = 0.85
        else:
            factor = 1.18
        self._zoom_at(event.x, event.y, self.zoom * factor)

    def toggle_pan(self):
        self.follow_switch = False
        self.camera_pan = not getattr(self, "camera_pan", False)
        self.pan_btn.config(text="Pan camera: on" if self.camera_pan else "Pan camera")

    def scene_up(self, _event):
        if getattr(self, "_cropping_drag", False):
            self._cropping_drag = False
            self._apply_crop()
            self.draw_scene()
            return
        drag = self.drag
        self.drag = None
        if drag and drag[1] >= 0:
            self._save_slot_placement(drag[1])
        if getattr(self, "_panning", False):
            self._panning = False
            self.remember_camera()

    def scene_pan_down(self, event):
        self._panning = True
        self._pan_drag = (event.x, event.y, self.pan_x, self.pan_y)

    def scene_pan_drag(self, event):
        if not getattr(self, "_pan_drag", None):
            return
        x0, y0, px, py = self._pan_drag
        self.pan_x = px - (event.x - x0) / self.zoom
        self.pan_y = py - (event.y - y0) / self.zoom
        self.remember_camera()
        self.draw_scene()

    def draw_scene(self):
        from PIL import Image, ImageTk

        if not hasattr(self, "scene"):
            return
        playing = self._play_started is not None
        now = (time.time() - self._play_started + self._play_offset) if playing else self.playhead
        if not getattr(self, "_panning", False):
            if getattr(self, "follow_switch", False):
                self._apply_program(now)
            else:
                self.apply_camera()
        width, height = self.scene_w, self.scene_h
        self.scene.delete("all")
        self.scene.create_rectangle(0, 0, width, height, fill="#1c2420", outline="")
        self._scene_photos = []
        bg_key = self.bg_image or (self.part_bg.get() or "coffee shop")
        if getattr(self, "_bg_key", None) != bg_key:
            self._bg_key = bg_key
            if self.bg_image and Path(self.bg_image).exists():
                self._bg_source = Image.open(self.bg_image).convert("RGBA")
            else:
                self._bg_source = paint_stage({"preset": bg_key}, (1280, 720)).convert("RGBA")
        source = self._bg_source
        bh = max(40, int(float(self.bg.get("h") or 1) * height))
        bw = max(40, int(bh * source.width / max(1, source.height)))
        bx, by, bw, bh = self._screen_box(float(self.bg.get("x") or 0) * width, float(self.bg.get("y") or 0) * height, bw, bh)
        bg = source.resize((bw, bh), Image.LANCZOS)
        bg_photo = ImageTk.PhotoImage(bg)
        self._scene_photos.append(bg_photo)
        self.scene.create_image(bx, by, image=bg_photo, anchor="nw")
        self.bg["_box"] = (bx, by, bw, bh)
        self._outline((bx, by, bw, bh), "#8d9a86", self.selection == ("bg",))
        for index, slot in enumerate(self.parts):
            if not slot["on"].get():
                slot["_box"] = None
                slot["_mouth_box"] = None
                continue
            path = slot.get("person") or ""
            if not path or not Path(path).exists():
                slot["_box"] = None
                slot["_mouth_box"] = None
                continue
            portrait = Image.open(path).convert("RGBA")
            ph = max(48, int(float(slot.get("h") or 0.5) * height))
            pw = max(24, int(ph * portrait.width / max(1, portrait.height)))
            portrait = portrait.resize((pw, ph), Image.LANCZOS)
            mouths = slot.get("mouths") or {}
            shape = mouth_at(self._play_cues.get(slot["name"].get().strip()) or [], now)
            mouth_path = mouths.get(shape) or mouths.get("closed") or ""
            ox = oy = mw = mh = 0
            if mouth_path and Path(mouth_path).exists():
                mouth = Image.open(mouth_path).convert("RGBA")
                mw = max(12, int(pw * float(slot.get("mouthScale") or 28) / 100))
                mh = max(8, int(mouth.height * mw / max(1, mouth.width)))
                mouth = mouth.resize((mw, mh), Image.LANCZOS)
                ox = int(pw * float(slot.get("mouthX") or 50) / 100) - mw // 2
                oy = int(ph * float(slot.get("mouthY") or 62) / 100) - mh // 2
                portrait.paste(mouth, (ox, oy), mouth)
            px, py, sw, sh = self._screen_box(
                float(slot.get("x") or 0) * width,
                float(slot.get("y") or 0) * height,
                pw,
                ph,
            )
            portrait = portrait.resize((sw, sh), Image.LANCZOS)
            photo = ImageTk.PhotoImage(portrait)
            self._scene_photos.append(photo)
            self.scene.create_image(px, py, image=photo, anchor="nw")
            slot["_box"] = (px, py, sw, sh)
            if mw:
                mouth_box = (
                    px + int(ox * self.zoom),
                    py + int(oy * self.zoom),
                    max(1, int(mw * self.zoom)),
                    max(1, int(mh * self.zoom)),
                )
            else:
                mouth_box = None
            slot["_mouth_box"] = mouth_box
            self._outline((px, py, sw, sh), "#c45c26", self.selection == ("person", index))
            if mouth_box:
                self._outline(mouth_box, "#f6f1e7", self.selection == ("mouth", index))
        self._draw_table(width, height)
        fg_path = self.fg.get("path") or ""
        self.fg["_box"] = None
        if fg_path and Path(fg_path).exists():
            front = Image.open(fg_path).convert("RGBA")
            fh = max(24, int(float(self.fg.get("h") or 0.4) * height))
            fw = max(24, int(fh * front.width / max(1, front.height)))
            fx, fy, fw, fh = self._screen_box(
                float(self.fg.get("x") or 0) * width,
                float(self.fg.get("y") or 0) * height,
                fw,
                fh,
            )
            front = front.resize((fw, fh), Image.LANCZOS)
            photo = ImageTk.PhotoImage(front)
            self._scene_photos.append(photo)
            self.scene.create_image(fx, fy, image=photo, anchor="nw")
            self.fg["_box"] = (fx, fy, fw, fh)
            self._outline((fx, fy, fw, fh), "#d4b483", self.selection == ("fg",))
        if self._crop_rect and not self._play_started:
            x0, y0, x1, y1 = self._crop_rect
            self.scene.create_rectangle(x0, y0, x1, y1, outline="#f6f1e7", dash=(4, 3), width=2)
        self.draw_track()

    def _draw_table(self, width, height):
        tx, ty, tw, th = self._screen_box(0, height * 0.68, width, height * 0.34)
        self.scene.create_rectangle(tx, ty, tx + tw, ty + max(8, int(th * 0.16)), fill="#c4a27a", outline="")
        self.scene.create_rectangle(tx, ty + int(th * 0.12), tx + tw, ty + th + 8, fill="#6b4228", outline="")
        self.scene.create_rectangle(tx + int(tw * 0.08), ty + int(th * 0.55), tx + int(tw * 0.14), ty + th, fill="#4a2c18", outline="")
        self.scene.create_rectangle(tx + int(tw * 0.86), ty + int(th * 0.55), tx + int(tw * 0.92), ty + th, fill="#4a2c18", outline="")

    def _save_slot_placement(self, index):
        if not (0 <= index < len(self.parts)):
            return
        slot = self.parts[index]
        cast_id = slot.get("cast_id")
        if not cast_id:
            return
        try:
            update_placement(
                cast_id,
                float(slot["mouthX"]),
                float(slot["mouthY"]),
                float(slot["mouthScale"]),
                float(slot["x"]),
                float(slot["y"]),
                float(slot["h"]),
            )
        except FileNotFoundError:
            return

    def _outline(self, box, color, selected):
        if self._play_started:
            return
        x, y, w, h = box
        self.scene.create_rectangle(x, y, x + w, y + h, outline=color, width=3 if selected else 1)
        handle = 8 if selected else 6
        self.scene.create_rectangle(x + w - handle, y + h - handle, x + w, y + h, fill=color, outline="")
        if selected:
            self.scene.create_text(x + 4, y + 2, text="selected", anchor="nw", fill=color, font=("Helvetica", 11, "bold"))

    def _clock(self, seconds):
        seconds = max(0, int(seconds))
        return f"{seconds // 60}:{seconds % 60:02d}"

    def _track_x(self, t):
        span = max(0.5, self.view_span)
        return int((t - self.view_start) / span * (self.scene_w - 16) + 8)

    def track_time(self, x):
        span = max(0.5, self.view_span)
        t = self.view_start + (x - 8) / max(1, self.scene_w - 16) * span
        return max(0.0, min(float(self._play_duration or t), t))

    def track_down(self, event):
        self.stop_play()
        self.playhead = self.track_time(event.x)
        self.draw_scene()

    def track_drag(self, event):
        self.playhead = self.track_time(event.x)
        self.draw_scene()

    def draw_track(self):
        if not hasattr(self, "track"):
            return
        colors = ("#c45c26", "#d4b483", "#8d9a86", "#6d8a9a", "#a36b7c", "#c4a35a")
        width, height = self.scene_w, 64
        self.track.delete("all")
        self.track.create_rectangle(0, 0, width, height, fill="#141a17", outline="")
        duration = max(1.0, float(self._play_duration or 60))
        self.view_span = max(2.0, min(duration, self.view_span))
        self.view_start = max(0.0, min(duration - self.view_span, self.view_start))
        names = list((self._play_cues or {}).keys())
        rows = max(1, len(names))
        row_h = (height - 8) / rows
        if not names:
            self.track.create_text(12, height / 2, text="Playhead", anchor="w", fill="#f6f1e7", font=("Helvetica", 11))
        for index, name in enumerate(names):
            top = 4 + index * row_h
            self.track.create_text(8, top, text=name[:12], anchor="nw", fill="#f6f1e7", font=("Helvetica", 9))
            for cue in self._play_cues.get(name) or []:
                x0 = self._track_x(float(cue.get("start") or 0))
                x1 = self._track_x(float(cue.get("end") or 0))
                if x1 < 8 or x0 > width - 8:
                    continue
                self.track.create_rectangle(
                    max(8, x0), top + 14, min(width - 8, max(x0 + 2, x1)), top + row_h - 2,
                    fill=colors[index % len(colors)], outline="",
                )
        for key in self.camera_keys:
            mark = self._track_x(key["t"])
            self.track.create_oval(mark - 4, height - 10, mark + 4, height - 2, fill="#d4b483", outline="")
        px = self._track_x(self.playhead)
        self.track.create_line(px, 0, px, height, fill="#f6f1e7", width=2)
        self.track.create_polygon(px - 7, 0, px + 7, 0, px, 12, fill="#f6f1e7", outline="")
        self.track.create_text(
            width - 8, 4,
            text=f"{self._clock(self.playhead)} / {self._clock(duration)}",
            anchor="ne", fill="#f6f1e7", font=("Helvetica", 10),
        )

    def _scene_hit(self, event):
        box = self.fg.get("_box")
        if box and self.fg.get("path"):
            px, py, pw, ph = box
            if px + pw - 22 <= event.x <= px + pw + 8 and py + ph - 22 <= event.y <= py + ph + 8:
                return "fg-size", -1
            if px <= event.x <= px + pw and py <= event.y <= py + ph:
                return "fg-move", -1
        for index in range(len(self.parts) - 1, -1, -1):
            slot = self.parts[index]
            box = slot.get("_box")
            if not box:
                continue
            px, py, pw, ph = box
            mouth = slot.get("_mouth_box")
            if mouth:
                mx, my, mw, mh = mouth
                if mx + mw - 18 <= event.x <= mx + mw + 8 and my + mh - 18 <= event.y <= my + mh + 8:
                    return "mouth-size", index
                if mx <= event.x <= mx + mw and my <= event.y <= my + mh:
                    return "mouth", index
            if px + pw - 22 <= event.x <= px + pw + 8 and py + ph - 22 <= event.y <= py + ph + 8:
                return "resize", index
            if px <= event.x <= px + pw and py <= event.y <= py + ph:
                return "move", index
        box = self.bg.get("_box")
        if box:
            px, py, pw, ph = box
            if px + pw - 22 <= event.x <= px + pw + 8 and py + ph - 22 <= event.y <= py + ph + 8:
                return "bg-size", -2
            if px <= event.x <= px + pw and py <= event.y <= py + ph:
                return "bg-move", -2
        return None

    def toggle_crop(self):
        if not self.selection:
            messagebox.showinfo("Select a picture", "Click a picture first. Its outline shows what will be cropped.")
            return
        self.cropping = not self.cropping
        self._crop_rect = None
        self.crop_btn.config(text="Crop: drag" if self.cropping else "Crop")
        self.draw_scene()

    def _selection_box(self):
        kind = (self.selection or (None,))[0]
        if kind == "bg":
            return self.bg.get("_box")
        if kind == "fg":
            return self.fg.get("_box")
        if kind in ("person", "mouth") and len(self.selection) > 1:
            slot = self.parts[self.selection[1]]
            return slot.get("_mouth_box") if kind == "mouth" else slot.get("_box")
        return None

    def _apply_crop(self):
        from PIL import Image

        if not self._crop_rect or not self.selection:
            return
        box = self._selection_box()
        if not box:
            return
        bx, by, bw, bh = box
        x0, y0, x1, y1 = self._crop_rect
        left, right = sorted((max(bx, min(bx + bw, x0)), max(bx, min(bx + bw, x1))))
        top, bottom = sorted((max(by, min(by + bh, y0)), max(by, min(by + bh, y1))))
        if right - left < 8 or bottom - top < 8:
            return
        kind = self.selection[0]
        if kind == "bg":
            image = self._bg_source
        elif kind == "fg":
            image = Image.open(self.fg["path"]).convert("RGBA")
        else:
            slot = self.parts[self.selection[1]]
            path = slot.get("mouths", {}).get("closed") if kind == "mouth" else slot.get("person")
            if kind == "mouth":
                shape = mouth_at(self._play_cues.get(slot["name"].get().strip()) or [], self.playhead)
                path = (slot.get("mouths") or {}).get(shape) or path
            if not path or not Path(path).exists():
                return
            image = Image.open(path).convert("RGBA")
        ix0 = int((left - bx) / max(1, bw) * image.width)
        iy0 = int((top - by) / max(1, bh) * image.height)
        ix1 = int((right - bx) / max(1, bw) * image.width)
        iy1 = int((bottom - by) / max(1, bh) * image.height)
        if ix1 - ix0 < 2 or iy1 - iy0 < 2:
            return
        cropped = image.crop((ix0, iy0, ix1, iy1))
        dest = SUPPORT / "crops"
        dest.mkdir(parents=True, exist_ok=True)
        file = dest / f"{uuid.uuid4().hex}.png"
        cropped.save(file)
        saved = str(file)
        if kind == "bg":
            self.bg_image = saved
            self._bg_key = None
        elif kind == "fg":
            self.fg["path"] = saved
        elif kind == "mouth":
            slot = self.parts[self.selection[1]]
            mouths = slot.setdefault("mouths", {})
            shape = mouth_at(self._play_cues.get(slot["name"].get().strip()) or [], self.playhead)
            key = shape if shape in mouths else next(iter(mouths), shape)
            mouths[key] = saved
        else:
            self.parts[self.selection[1]]["person"] = saved
        self.cropping = False
        self._crop_rect = None
        self.crop_btn.config(text="Crop")

    def scene_down(self, event):
        if getattr(self, "camera_pan", False) or (event.state & 0x0001):
            self.scene_pan_down(event)
            return
        if self.cropping and self.selection:
            box = self._selection_box()
            if box and box[0] <= event.x <= box[0] + box[2] and box[1] <= event.y <= box[1] + box[3]:
                self._crop_rect = (event.x, event.y, event.x, event.y)
                self._cropping_drag = True
                return
        self._cropping_drag = False
        hit = self._scene_hit(event)
        if not hit:
            self.drag = None
            self.selection = None
            self.draw_scene()
            return
        kind, index = hit
        if kind in ("mouth", "mouth-size"):
            self.selection = ("mouth", index)
        elif index == -1:
            self.selection = ("fg",)
        elif index == -2:
            self.selection = ("bg",)
        else:
            self.selection = ("person", index)
        if index < 0:
            layer = self.fg if index == -1 else self.bg
            self.drag = (
                kind, index, event.x, event.y,
                float(layer["x"]), float(layer["y"]), float(layer["h"]),
                0, 0, 0, layer.get("_box"),
            )
            self.draw_scene()
            return
        self.scene_index = index
        slot = self.parts[index]
        self.drag = (
            kind,
            index,
            event.x,
            event.y,
            float(slot["x"]),
            float(slot["y"]),
            float(slot["h"]),
            float(slot["mouthX"]),
            float(slot["mouthY"]),
            float(slot["mouthScale"]),
            slot.get("_box"),
        )
        self.draw_scene()

    def scene_drag(self, event):
        if getattr(self, "_cropping_drag", False) and self._crop_rect:
            x0, y0 = self._crop_rect[0], self._crop_rect[1]
            self._crop_rect = (x0, y0, event.x, event.y)
            self.draw_scene()
            return
        if getattr(self, "_panning", False):
            self.scene_pan_drag(event)
            return
        if not self.drag:
            return
        kind, index, x0, y0, sx, sy, sh, mx, my, ms, box = self.drag
        if index < 0:
            layer = self.fg if index == -1 else self.bg
            if box and kind in ("fg-size", "bg-size"):
                grow = max((event.x - x0) / max(1, box[2]), (event.y - y0) / max(1, box[3]))
                layer["h"] = max(0.08, min(3.0, sh * (1 + grow)))
            elif kind in ("fg-move", "bg-move"):
                layer["x"] = sx + (event.x - x0) / self.zoom / self.scene_w
                layer["y"] = sy + (event.y - y0) / self.zoom / self.scene_h
            self.draw_scene()
            return
        slot = self.parts[index]
        if kind == "move":
            slot["x"] = sx + (event.x - x0) / self.zoom / self.scene_w
            slot["y"] = sy + (event.y - y0) / self.zoom / self.scene_h
        elif kind == "resize" and box:
            grow = max((event.x - x0) / max(1, box[2]), (event.y - y0) / max(1, box[3]))
            slot["h"] = max(0.08, min(2.0, sh * (1 + grow)))
        elif box and kind == "mouth":
            slot["mouthX"] = max(8, min(92, mx + (event.x - x0) / max(1, box[2]) * 100))
            slot["mouthY"] = max(8, min(92, my + (event.y - y0) / max(1, box[3]) * 100))
        elif box and kind == "mouth-size":
            grow = max((event.x - x0) / 80, (event.y - y0) / 80)
            slot["mouthScale"] = max(4, min(120, ms * (1 + grow)))
        self.draw_scene()

    def play_episode(self):
        ready = []
        for slot in self.parts:
            if slot.get("audio") and slot.get("person") and slot["on"].get():
                ready.append({
                    "name": slot["name"].get().strip() or "Person",
                    "audio": slot["audio"],
                })
        if not ready:
            messagebox.showwarning("Add audio", "Each person you want to hear needs an audio file and a picture.")
            return
        self.play_btn.config(state="disabled")
        self.show_busy("Getting the mouths ready")
        threading.Thread(target=self._prepare_play, args=(ready,), daemon=True).start()

    def _prepare_play(self, people):
        try:
            from podcast_processor import _mix_wav, _pcm

            raws = []
            cues = {}
            duration = 1
            out = Path.home() / "Desktop" / "Podcast Processor"
            out.mkdir(parents=True, exist_ok=True)
            total = len(people)
            for index, person in enumerate(people):
                self.root.after(0, lambda i=index, n=total, name=person["name"]: self.show_progress((i + 0.2) / n, f"Rhubarb is reading {name}"))
                raw = _pcm(Path(person["audio"]))
                raws.append(raw)
                duration = max(duration, (len(raw) / 2) / 16000)

                def report(amount, label, name=person["name"], i=index, n=total):
                    self.root.after(0, lambda a=amount, lab=label: self.show_progress((i + a) / n, f"{name}: {lab}"))

                try:
                    cues[person["name"]] = build_cues(person["audio"], {"language": "en", "segments": []}, report)
                except Exception as exc:
                    cues[person["name"]] = self._talking_cues(raw)
                    self.root.after(0, lambda e=exc, name=person["name"]: self.write(f"{name}: Rhubarb did not finish, so the mouth follows the volume. {e}\n"))
            mix = out / "scene-mix.wav"
            _mix_wav(raws, mix)
            self.root.after(0, lambda: self._start_play(str(mix), cues, duration))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._fail(e))
            self.root.after(0, lambda: self.play_btn.config(state="normal"))

    def _talking_cues(self, raw):
        import array

        samples = array.array("h")
        samples.frombytes(raw)
        frame = 800
        if len(samples) < frame:
            return []
        levels = []
        for start in range(0, len(samples) - frame, frame):
            acc = 0
            crossings = 0
            prev = 0
            for sample in samples[start : start + frame]:
                acc += sample * sample
                if (sample >= 0) != (prev >= 0):
                    crossings += 1
                prev = sample
            levels.append(((acc / frame) ** 0.5, crossings / frame))
        ordered = sorted(level for level, _cross in levels)
        noise = ordered[max(0, int(len(ordered) * 0.35) - 1)] or 1
        peak = ordered[min(len(ordered) - 1, int(len(ordered) * 0.92))] or noise * 4
        span = max(40, peak - noise)
        step = frame / 16000
        cues = []
        for index, (level, rate) in enumerate(levels):
            if level < max(40, noise * 1.6):
                mouth = "closed"
            else:
                openness = (level - noise) / span
                if rate > 0.16 and openness > 0.35:
                    mouth = "teeth"
                elif openness > 0.72:
                    mouth = "wide"
                elif openness > 0.42:
                    mouth = "round" if rate < 0.07 else "medium"
                elif openness > 0.18:
                    mouth = "small"
                else:
                    mouth = "closed"
            begin = index * step
            if cues and cues[-1]["mouth"] == mouth:
                cues[-1]["end"] = begin + step
            else:
                cues.append({"start": begin, "end": begin + step, "mouth": mouth})
        return cues

    def stop_play(self):
        self._play_token += 1
        self._play_started = None
        player = getattr(self, "_player", None)
        if player is not None and player.poll() is None:
            player.terminate()
        self._player = None
        if hasattr(self, "scene"):
            self.draw_scene()

    def _start_play(self, mix, cues, duration):
        self.stop_play()
        self._play_cues = cues
        self._play_duration = duration
        if self.view_span > duration or abs(self.view_span - 60) < 0.1:
            self.view_span = duration
            self.view_start = 0
        audio, offset = self._audio_from(mix)
        self._play_offset = offset
        self.playhead = offset
        self._play_started = time.time()
        self.play_btn.config(state="normal")
        self.show_done("Playing")
        if sys.platform == "darwin":
            self._player = subprocess.Popen(["afplay", audio])
        else:
            self._player = None
        token = self._play_token
        self._tick_play(token)

    def _audio_from(self, mix):
        start = max(0.0, float(self.playhead))
        if start < 0.3:
            return mix, 0.0
        try:
            import imageio_ffmpeg

            dest = Path(mix).with_name("scene-from-here.wav")
            subprocess.run(
                [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-ss", f"{start:.3f}", "-i", mix, str(dest)],
                check=True,
                capture_output=True,
            )
            return str(dest), start
        except Exception:
            return mix, 0.0

    def _tick_play(self, token):
        if token != self._play_token or self._play_started is None:
            return
        self.playhead = time.time() - self._play_started + self._play_offset
        if self.playhead > self._play_duration:
            self.playhead = self._play_duration
            self.stop_play()
            self.show_done("Ready")
            return
        if self.playhead < self.view_start or self.playhead > self.view_start + self.view_span:
            self.view_start = max(0.0, self.playhead - self.view_span * 0.15)
        self.draw_scene()
        self.root.after(90, lambda: self._tick_play(token))

    def remove_part(self, index):
        if 0 <= index < len(self.parts):
            self.parts.pop(index)
            self.refresh_parts()

    def refresh_parts(self):
        for child in self.parts_box.winfo_children():
            child.destroy()
        for index, slot in enumerate(self.parts):
            row = tk.Frame(self.parts_box, bg=BG)
            row.pack(fill="x", pady=2)
            ttk.Checkbutton(row, text="On", variable=slot["on"], command=self.draw_scene).pack(side="left", padx=(0, 4))
            ttk.Button(row, text=slot["name"].get() or "Person", command=lambda i=index: self.open_person(i)).pack(side="left")
            bits = []
            if slot.get("audio"):
                bits.append("audio")
            if slot.get("person"):
                bits.append("profile")
            if slot.get("mouths"):
                bits.append("mouth")
            tk.Label(row, text=", ".join(bits) if bits else "not set up", bg=BG, fg=INK).pack(side="left", padx=8)
        if hasattr(self, "scene"):
            self.draw_scene()
        self.refresh_switch_buttons()

    def refresh_switch_buttons(self):
        if not hasattr(self, "switch_box"):
            return
        for child in self.switch_box.winfo_children():
            child.destroy()
        ttk.Button(self.switch_box, text="Wide", command=lambda: self.cut_to("wide")).pack(side="left", padx=2)
        for slot in self.parts:
            if not slot["on"].get():
                continue
            name = slot["name"].get().strip() or "Person"
            ttk.Button(self.switch_box, text=name, command=lambda n=name: self.cut_to(n)).pack(side="left", padx=2)

    def cut_to(self, shot):
        if self._play_started is not None:
            t = time.time() - self._play_started + self._play_offset
            self.playhead = t
        else:
            t = float(self.playhead)
        self.cuts = [cut for cut in self.cuts if abs(cut["t"] - t) > 0.08]
        self.cuts.append({"t": max(0.0, t), "shot": shot})
        self.cuts.sort(key=lambda cut: cut["t"])
        self.program = shot
        self.follow_switch = True
        self._apply_program(t)
        self.draw_scene()

    def _apply_program(self, t):
        from podcast_video import camera_for, shot_at

        shot = shot_at(self.cuts, t)
        self.program = shot
        people = [self._broadcast_person(slot) for slot in self.parts if slot["on"].get() and slot.get("person")]
        self.zoom, self.pan_x, self.pan_y = camera_for(shot, people, self.scene_w, self.scene_h)
        if hasattr(self, "on_air"):
            self.on_air.config(text=f"ON AIR   {shot if shot != 'wide' else 'Wide'}")

    def _broadcast_person(self, slot):
        return {
            "name": slot["name"].get().strip() or "Person",
            "image": slot.get("person") or "",
            "mouths": dict(slot.get("mouths") or {}),
            "x": float(slot.get("x") or 0),
            "y": float(slot.get("y") or 0),
            "h": float(slot.get("h") or 0.7),
            "mouthX": float(slot.get("mouthX") or 50),
            "mouthY": float(slot.get("mouthY") or 42),
            "mouthScale": float(slot.get("mouthScale") or 18),
            "audio": slot.get("audio") or "",
        }

    def export_switched(self):
        people = [self._broadcast_person(slot) for slot in self.parts if slot["on"].get() and slot.get("person")]
        if not people:
            messagebox.showwarning("Nothing to export", "Turn on at least one person who has a picture.")
            return
        self.show_busy("Exporting the switched show")
        cuts = [dict(cut) for cut in self.cuts]
        cues = dict(getattr(self, "_play_cues", {}) or {})
        bg = self.bg_image or (self.part_bg.get() or "coffee shop")
        threading.Thread(target=self._export_switched, args=(people, cuts, cues, bg), daemon=True).start()

    def _export_switched(self, people, cuts, cues, bg):
        try:
            from podcast_processor import _mix_wav, _pcm
            from podcast_video import render_broadcast

            raws = []
            duration = 8.0
            for person in people:
                if not person.get("audio"):
                    continue
                if person["name"] not in cues:
                    try:
                        cues[person["name"]] = build_cues(person["audio"], {"language": "en", "segments": []})
                    except Exception:
                        raw = _pcm(Path(person["audio"]))
                        cues[person["name"]] = self._talking_cues(raw)
                raw = _pcm(Path(person["audio"]))
                raws.append(raw)
                duration = max(duration, (len(raw) / 2) / 16000)
            out = Path.home() / "Desktop" / "Podcast Processor"
            out.mkdir(parents=True, exist_ok=True)
            audio = None
            if raws:
                audio = out / "switched-mix.wav"
                _mix_wav(raws, audio)
            dest = out / "switched-show.mp4"

            def report(done, total):
                self.root.after(0, lambda d=done, n=total: self.show_progress(d / max(1, n), f"Frame {d} of {n}"))

            render_broadcast(people, cuts, cues, dest, background=bg, audio_path=str(audio) if audio else None, duration=duration, progress=report)
            self.root.after(0, lambda: self._switched_done(dest))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._fail(e))

    def _switched_done(self, dest):
        self.show_done("Switched show exported")
        self.write(f"Switched MP4 saved to {dest}\n")
        messagebox.showinfo("Switched show", f"The MP4 is on your Desktop:\n{dest}")

    def open_person(self, index):
        if not (0 <= index < len(self.parts)):
            return
        slot = self.parts[index]
        win = tk.Toplevel(self.root)
        win.title(slot["name"].get() or "Person")
        win.configure(bg=BG)
        win.transient(self.root)
        tk.Label(win, text="Name", bg=BG, fg=INK).pack(anchor="w", padx=16, pady=(12, 0))
        ttk.Entry(win, textvariable=slot["name"], width=28).pack(anchor="w", padx=16)
        audio_label = tk.Label(win, text=Path(slot["audio"]).name if slot.get("audio") else "No audio yet", bg=BG, fg=INK)
        profile_label = tk.Label(win, text=Path(slot["person"]).name if slot.get("person") else "No profile yet", bg=BG, fg=INK)
        mouth_label = tk.Label(win, text=self._mouth_status(slot), bg=BG, fg=INK)

        def choose_audio():
            path = filedialog.askopenfilename(parent=win, filetypes=[("Audio", "*.mp3 *.wav *.m4a *.mp4")])
            if path:
                slot["audio"] = path
                audio_label.config(text=Path(path).name)
                self.refresh_parts()

        def choose_profile():
            path = filedialog.askopenfilename(parent=win, filetypes=[("Picture", "*.png *.jpg *.jpeg *.webp")])
            if path:
                slot["person"] = path
                profile_label.config(text=Path(path).name)
                self.refresh_parts()

        def choose_mouth():
            self.pick_part_mouths(index)
            mouth_label.config(text=self._mouth_status(slot))
            self.draw_scene()

        tk.Label(win, text="Audio", bg=BG, fg=INK).pack(anchor="w", padx=16, pady=(12, 0))
        ttk.Button(win, text="Choose audio", command=choose_audio).pack(anchor="w", padx=16)
        audio_label.pack(anchor="w", padx=16)
        tk.Label(win, text="Profile", bg=BG, fg=INK).pack(anchor="w", padx=16, pady=(12, 0))
        ttk.Button(win, text="Choose profile", command=choose_profile).pack(anchor="w", padx=16)
        profile_label.pack(anchor="w", padx=16)
        tk.Label(win, text="Mouth", bg=BG, fg=INK).pack(anchor="w", padx=16, pady=(12, 0))
        ttk.Button(win, text="Choose the 6-piece mouth image", command=choose_mouth).pack(anchor="w", padx=16)
        mouth_label.pack(anchor="w", padx=16)
        ttk.Button(win, text="Done", command=win.destroy).pack(anchor="w", padx=16, pady=16)

    def _mouth_status(self, slot):
        count = len(slot.get("mouths") or {})
        return f"{count} of 6 mouths" if count else "No mouth sheet yet"

    def scene_open_person(self, event):
        hit = self._scene_hit(event)
        if hit and hit[1] >= 0 and hit[0] in ("move", "mouth", "mouth-size", "resize"):
            self.open_person(hit[1])

    def open_background(self):
        win = tk.Toplevel(self.root)
        win.title("Background")
        win.configure(bg=BG)
        win.transient(self.root)
        tk.Label(win, text="This layer sits behind everyone. Drag its corner to resize it.", bg=BG, fg=INK).pack(anchor="w", padx=16, pady=(12, 0))
        room = ttk.Combobox(win, values=("coffee shop", "library"), width=16, state="readonly")
        room.set(self.part_bg.get() or "coffee shop")
        room.pack(anchor="w", padx=16, pady=8)

        def use_room(_event=None):
            self.part_bg.set(room.get())
            self.bg_image = ""
            self.draw_scene()

        room.bind("<<ComboboxSelected>>", use_room)
        status = tk.Label(win, text=Path(self.bg_image).name if self.bg_image else "Using the room", bg=BG, fg=INK)
        status.pack(anchor="w", padx=16)

        def choose():
            path = filedialog.askopenfilename(parent=win, filetypes=[("Picture", "*.png *.jpg *.jpeg *.webp")])
            if path:
                self.bg_image = path
                status.config(text=Path(path).name)
                self.draw_scene()

        def clear():
            self.bg_image = ""
            status.config(text="Using the room")
            self.draw_scene()

        ttk.Button(win, text="Choose a picture", command=choose).pack(anchor="w", padx=16, pady=(8, 0))
        ttk.Button(win, text="Use the room instead", command=clear).pack(anchor="w", padx=16, pady=4)
        ttk.Button(win, text="Done", command=win.destroy).pack(anchor="w", padx=16, pady=12)

    def open_foreground(self):
        win = tk.Toplevel(self.root)
        win.title("Foreground")
        win.configure(bg=BG)
        win.transient(self.root)
        tk.Label(win, text="This layer sits in front of the people. Drag it to move it, and drag its corner to resize it.", bg=BG, fg=INK).pack(anchor="w", padx=16, pady=(12, 0))
        status = tk.Label(win, text=Path(self.fg["path"]).name if self.fg.get("path") else "No foreground yet", bg=BG, fg=INK)
        status.pack(anchor="w", padx=16, pady=8)

        def choose():
            path = filedialog.askopenfilename(parent=win, filetypes=[("Picture", "*.png *.jpg *.jpeg *.webp")])
            if path:
                self.fg["path"] = path
                status.config(text=Path(path).name)
                self.draw_scene()

        def clear():
            self.fg["path"] = ""
            status.config(text="No foreground yet")
            self.draw_scene()

        ttk.Button(win, text="Choose a picture", command=choose).pack(anchor="w", padx=16)
        ttk.Button(win, text="Remove foreground", command=clear).pack(anchor="w", padx=16, pady=4)
        ttk.Button(win, text="Done", command=win.destroy).pack(anchor="w", padx=16, pady=12)

    def pick_part_audio(self, index):
        path = filedialog.askopenfilename(filetypes=[("Audio", "*.mp3 *.wav *.m4a *.mp4")])
        if path and 0 <= index < len(self.parts):
            self.parts[index]["audio"] = path
            self.refresh_parts()

    def pick_part_person(self, index):
        path = filedialog.askopenfilename(filetypes=[("Picture", "*.png *.jpg *.jpeg *.webp")])
        if path and 0 <= index < len(self.parts):
            self.parts[index]["person"] = path
            self.refresh_parts()

    def pick_part_mouths(self, index):
        path = filedialog.askopenfilename(
            title="Mouth sheet: six mouths, three across and two down",
            filetypes=[("Pictures", "*.png *.jpg *.jpeg *.webp")],
        )
        if not path or not (0 <= index < len(self.parts)):
            return
        dest = SUPPORT / "mouth-sheets" / f"{index}-{Path(path).stem}"
        try:
            mouths = parse_mouth_sheet(path, dest)
        except Exception as exc:
            messagebox.showerror("Could not read that mouth sheet", str(exc))
            return
        self.parts[index]["mouths"] = mouths
        self.refresh_parts()

    def export_group(self):
        people = []
        for slot in self.parts:
            if not slot["on"].get():
                continue
            people.append({
                "name": slot["name"].get().strip() or "Person",
                "audio": slot["audio"],
                "person": slot["person"],
                "mouths": dict(slot["mouths"]),
            })
        if not any(person["audio"] and person["person"] for person in people):
            messagebox.showwarning("Missing parts", "Each person needs a picture and an audio file.")
            return
        background = bundled_background(self.part_bg.get() or "coffee shop")
        self.show_busy("Exporting the group")
        threading.Thread(
            target=self._export_group,
            args=(people, str(background) if background else ""),
            daemon=True,
        ).start()

    def _export_group(self, people, background):
        try:
            dest_root = Path.home() / "Desktop" / "Podcast Processor" / "group-opentoonz"
            cues = {}
            for person in people:
                if not person.get("audio"):
                    continue
                try:
                    cues[person["name"]] = build_cues(person["audio"], {"language": "en", "segments": []})
                except Exception as exc:
                    cues[person["name"]] = []
                    self.root.after(0, lambda e=exc, name=person["name"]: self.write(f"{name} will use simple mouth timing: {e}\n"))
            dest = export_parts(people, dest_root, background or None, cues)
            app = launch_opentoonz(dest)
            self.root.after(0, lambda: self._opentoonz_done(dest, app))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._fail(e))

    def choose_audio(self):
        path = filedialog.askopenfilename(filetypes=[("Audio", "*.mp3 *.wav *.m4a *.mp4")])
        if path:
            self.tracks = []
            self.audio = path
            self.audio_label.config(text=Path(path).name, font=("Helvetica", 16, "bold"))
            self.show_done("Audio ready")

    def choose_tracks(self):
        paths = filedialog.askopenfilenames(filetypes=[("Audio", "*.mp3 *.wav *.m4a *.mp4")])
        if not paths:
            return
        self.tracks = list(paths)
        self.audio = None
        names = ", ".join(Path(path).stem for path in self.tracks)
        self.audio_label.config(text=names, font=("Helvetica", 16, "bold"))
        self.show_done("Separate tracks ready")

    def start_process(self):
        if not self.audio and not self.tracks:
            messagebox.showwarning("Missing audio", "Choose an audio file, or one file per person.")
            return
        if self.tracks:
            self.persist_keys()
            self.go.config(state="disabled")
            self.video_btn.config(state="disabled")
            self.toonz_btn.config(state="disabled")
            self.show_busy("Reading each person")
            threading.Thread(target=self._process_tracks, args=(list(self.tracks),), daemon=True).start()
            return
        token = self.hf.get().strip()
        if not token:
            messagebox.showwarning("Missing token", "Paste your Hugging Face token.")
            return
        self.persist_keys()
        os.environ["HF_TOKEN"] = token
        self.go.config(state="disabled")
        self.video_btn.config(state="disabled")
        self.toonz_btn.config(state="disabled")
        self.show_busy("Finding speakers")
        audio = self.audio
        low = int(self.min_sp.get())
        high = int(self.max_sp.get())
        threading.Thread(target=self._process, args=(audio, low, high), daemon=True).start()

    def _process_tracks(self, paths):
        try:
            out = Path.home() / "Desktop" / "Podcast Processor"
            def report(amount, label):
                self.root.after(0, lambda a=amount, s=label: self.show_progress(a, s))

            result = process_tracks(paths, str(out), progress=report)
            self.root.after(0, lambda: self._processed(result, out))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._fail(e))

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
        if result.get("mixed_audio"):
            self.audio = result["mixed_audio"]
        self.go.config(state="normal")
        self.video_btn.config(state="normal")
        self.toonz_btn.config(state="normal")
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

    def start_opentoonz(self):
        if not self.result or not self.audio:
            messagebox.showwarning("Find speakers first", "Choose the audio and find the speakers first.")
            return
        self.toonz_btn.config(state="disabled")
        self.show_busy("Preparing OpenToonz")
        names = {}
        for sp, var in self.speaker_vars.items():
            picked = var.get()
            names[sp] = picked if picked != "(simple card)" else sp
        threading.Thread(
            target=self._opentoonz,
            args=(self.audio, self.result, names, self._cast_for_speakers()),
            daemon=True,
        ).start()

    def _opentoonz(self, audio, result, names, cast):
        try:
            try:
                cues = build_cues(audio, result)
            except Exception:
                cues = []
            dest = Path.home() / "Desktop" / "Podcast Processor" / f"{Path(audio).stem}_opentoonz"
            export_opentoonz(audio, result, names, cast, cues, dest)
            app = launch_opentoonz(dest)
            self.root.after(0, lambda: self._opentoonz_done(dest, app))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._fail(e))

    def _opentoonz_done(self, dest, app):
        self.toonz_btn.config(state="normal")
        self.show_done("OpenToonz project ready")
        if app is None:
            messagebox.showinfo(
                "OpenToonz is not installed",
                "The episode is saved here:\n"
                f"{dest}\n\n"
                "Install the free OpenToonz app, then click Open in OpenToonz again.",
            )
            return
        messagebox.showinfo(
            "OpenToonz",
            "OpenToonz is opening this episode.\n\n"
            "Each person has a folder of mouth drawings and a lip-sync file. "
            "Load their pictures, then choose Level, Apply Lip Sync Data to Column, and pick the .dat file in that folder.",
        )

    def _video(self, audio, result, names, cast):
        try:
            out = Path.home() / "Desktop" / "Podcast Processor"
            out.mkdir(parents=True, exist_ok=True)
            dest = out / f"{Path(audio).stem}_cartoon.mp4"
            def report(amount, label):
                self.root.after(0, lambda a=amount, s=label: self.show_progress(a * 0.35, s))

            tracks = (result or {}).get("per_speaker_audio") or {}
            cues = None
            if tracks:
                cues = {}
                count = len(tracks)
                for index, (speaker, path) in enumerate(tracks.items()):
                    partial = {
                        "language": "en",
                        "segments": [seg for seg in result.get("segments") or [] if seg.get("speaker") == speaker],
                    }
                    try:
                        cues[speaker] = build_cues(path, partial, report)
                    except Exception as exc:
                        cues[speaker] = []
                        self.root.after(0, lambda e=exc, name=speaker: self.write(f"Lip sync for {name} used a timer: {e}\n"))
                    self.root.after(0, lambda i=index, n=count: self.show_progress(0.2 + 0.15 * (i + 1) / n, "Matching mouths"))
            else:
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
        tk.Label(parent, text="Mouth shapes. Place people on the Episode scene.", bg=BG, fg=INK).pack(anchor="w", padx=8, pady=(8, 0))
        self.preview = tk.Label(parent, bg=BG, fg=INK)
        self.preview.pack(anchor="w", padx=8, pady=4)
        self.mouth_shape = tk.StringVar(value="closed")
        self.mouth_x = tk.DoubleVar(value=50)
        self.mouth_y = tk.DoubleVar(value=64)
        self.mouth_s = tk.DoubleVar(value=22)
        self.puppet_scale = tk.DoubleVar(value=100)
        shapes = tk.Frame(parent, bg=BG)
        shapes.pack(anchor="w", padx=8)
        for name in ("closed", "small", "medium", "wide", "round", "teeth"):
            ttk.Radiobutton(
                shapes, text=name, value=name, variable=self.mouth_shape,
                command=self.refresh_puppet_preview,
            ).pack(side="left")
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
        self._job_started = None
        self._pulse_on = False
        self.go.config(state="normal")
        self.video_btn.config(state="normal")
        self.toonz_btn.config(state="normal" if self.result else "disabled")
        self.bar.stop()
        self.bar.config(mode="determinate")
        self.bar["value"] = 0
        self.percent.config(text="0%")
        self.status.config(text="Something went wrong")
        self.write(f"\nError: {exc}\n")
        messagebox.showerror("Something went wrong", str(exc))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
