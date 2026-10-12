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
from podcast_video import preview_puppet, render_cartoon
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


class App:
    def __init__(self, root):
        self.root = root
        root.title("Podcast to Cartoon")
        root.geometry("980x820")
        root.configure(bg="#f3ecdf")
        self.audio = None
        self.result = None
        self.cast = []
        self.selected = None
        self.speaker_vars = {}
        self.sets = []
        self.preview_photo = None
        self.set_photo = None
        cfg = load_config()

        tk.Label(root, text="Podcast to Cartoon", font=("Helvetica", 20, "bold"), bg="#f3ecdf").pack(pady=(12, 2))
        tk.Label(
            root,
            text="Place each puppet, design the set, then make the video.",
            bg="#f3ecdf",
        ).pack()

        keys = tk.Frame(root, bg="#f3ecdf")
        keys.pack(pady=8)
        tk.Label(keys, text="Hugging Face token", bg="#f3ecdf").grid(row=0, column=0, sticky="w")
        self.hf = tk.Entry(keys, width=42, show="*")
        self.hf.grid(row=0, column=1, padx=6)
        if cfg.get("hf"):
            self.hf.insert(0, cfg["hf"])
        tk.Label(keys, text="xAI key (drawing only)", bg="#f3ecdf").grid(row=1, column=0, sticky="w")
        self.xai = tk.Entry(keys, width=42, show="*")
        self.xai.grid(row=1, column=1, padx=6, pady=4)
        if cfg.get("xai"):
            self.xai.insert(0, cfg["xai"])

        body = tk.Frame(root, bg="#f3ecdf")
        body.pack(fill="both", expand=True, padx=12, pady=6)
        left = tk.Frame(body, bg="#f3ecdf")
        left.pack(side="left", fill="y")
        tk.Label(left, text="Saved cast", bg="#f3ecdf", font=("Helvetica", 13, "bold")).pack(anchor="w")
        self.cast_list = tk.Listbox(left, width=28, height=12)
        self.cast_list.pack(pady=4)
        self.cast_list.bind("<<ListboxSelect>>", self.on_select)
        row = tk.Frame(left, bg="#f3ecdf")
        row.pack()
        tk.Button(row, text="Add headshot", command=self.add_headshot).pack(side="left", padx=2)
        tk.Button(row, text="Remove", command=self.remove_selected).pack(side="left", padx=2)
        tk.Label(left, text="Name", bg="#f3ecdf").pack(anchor="w", pady=(8, 0))
        self.name = tk.Entry(left, width=28)
        self.name.pack()
        tk.Label(left, text="Note for the drawing", bg="#f3ecdf").pack(anchor="w")
        self.note = tk.Entry(left, width=28)
        self.note.pack()
        tk.Button(left, text="Draw avatar", command=self.start_draw).pack(pady=4, fill="x")
        tk.Button(left, text="Cut mouths", command=self.start_mouths).pack(fill="x")
        tk.Button(left, text="Keep avatar", command=self.keep_selected).pack(pady=4, fill="x")

        right = tk.Frame(body, bg="#f3ecdf")
        right.pack(side="left", fill="both", expand=True, padx=(16, 0))
        book = ttk.Notebook(right)
        book.pack(fill="both", expand=True)
        episode = tk.Frame(book, bg="#f3ecdf")
        puppet = tk.Frame(book, bg="#f3ecdf")
        studio = tk.Frame(book, bg="#f3ecdf")
        book.add(episode, text="Episode")
        book.add(puppet, text="Puppet")
        book.add(studio, text="Set")
        tk.Button(episode, text="Choose audio", command=self.choose_audio).pack(anchor="w", padx=8, pady=(8, 0))
        self.audio_label = tk.Label(episode, text="No audio yet", bg="#f3ecdf")
        self.audio_label.pack(anchor="w", padx=8)
        spins = tk.Frame(episode, bg="#f3ecdf")
        spins.pack(anchor="w", padx=8, pady=4)
        tk.Label(spins, text="Min", bg="#f3ecdf").pack(side="left")
        self.min_sp = tk.Spinbox(spins, from_=2, to=8, width=4)
        self.min_sp.delete(0, "end")
        self.min_sp.insert(0, "4")
        self.min_sp.pack(side="left", padx=4)
        tk.Label(spins, text="Max", bg="#f3ecdf").pack(side="left")
        self.max_sp = tk.Spinbox(spins, from_=2, to=8, width=4)
        self.max_sp.delete(0, "end")
        self.max_sp.insert(0, "5")
        self.max_sp.pack(side="left", padx=4)
        self.go = tk.Button(episode, text="1. Find speakers", command=self.start_process)
        self.go.pack(anchor="w", padx=8, pady=4)
        self.assign = tk.Frame(episode, bg="#f3ecdf")
        self.assign.pack(anchor="w", fill="x", padx=8, pady=4)
        self.video_btn = tk.Button(episode, text="2. Make cartoon video", command=self.start_video, state="disabled")
        self.video_btn.pack(anchor="w", padx=8, pady=4)
        self.log = scrolledtext.ScrolledText(episode, height=12, width=70)
        self.log.pack(fill="both", expand=True, pady=6)
        self._build_puppet(puppet)
        self._build_set(studio)
        self.write("Kept avatars live in this Mac account and can be reused on the next episode.\n")
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
        self.write("Drawing avatar…\n")
        threading.Thread(target=self._draw, args=(loaded,), daemon=True).start()

    def _draw(self, loaded):
        try:
            blob = draw_avatar(loaded["photo"], self.xai.get().strip(), self.note.get().strip())
            keep_cast(
                loaded["id"],
                self.name.get().strip() or loaded.get("name"),
                self.note.get().strip(),
                Path(loaded["photo"]).read_bytes(),
                blob,
                float(loaded.get("mouthX") or 50),
                float(loaded.get("mouthY") or 64),
                float(loaded.get("mouthScale") or 22),
                None,
            )
            self.root.after(0, self._drew)
        except Exception as exc:
            self.root.after(0, lambda: self._fail(exc))

    def _drew(self):
        self.refresh_cast()
        self.write("Avatar drawn and kept.\n")

    def start_mouths(self):
        loaded = self.current()
        if not loaded or not loaded.get("avatar"):
            messagebox.showwarning("No avatar", "Draw the avatar before cutting mouths.")
            return
        self.persist_keys()
        self.write("Cutting mouths…\n")
        threading.Thread(target=self._mouths, args=(loaded,), daemon=True).start()

    def _mouths(self, loaded):
        try:
            mouths = draw_mouths(loaded["avatar"], self.xai.get().strip())
            keep_cast(
                loaded["id"],
                self.name.get().strip() or loaded.get("name"),
                self.note.get().strip(),
                Path(loaded["photo"]).read_bytes(),
                Path(loaded["avatar"]).read_bytes(),
                float(loaded.get("mouthX") or 50),
                float(loaded.get("mouthY") or 64),
                float(loaded.get("mouthScale") or 22),
                mouths,
            )
            self.root.after(0, lambda: self.write("Mouths cut and kept with this avatar.\n"))
        except Exception as exc:
            self.root.after(0, lambda: self._fail(exc))

    def choose_audio(self):
        path = filedialog.askopenfilename(filetypes=[("Audio", "*.mp3 *.wav *.m4a *.mp4")])
        if path:
            self.audio = path
            self.audio_label.config(text=Path(path).name)

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
        self.write("\nFinding speakers…\n")
        threading.Thread(target=self._process, daemon=True).start()

    def _process(self):
        try:
            out = Path.home() / "Desktop" / "Podcast Processor"
            result = process_audio(
                self.audio,
                str(out),
                model="small",
                min_speakers=int(self.min_sp.get()),
                max_speakers=int(self.max_sp.get()),
            )
            self.root.after(0, lambda: self._processed(result, out))
        except Exception as exc:
            self.root.after(0, lambda: self._fail(exc))

    def _processed(self, result, out):
        self.result = result
        self.go.config(state="normal")
        self.video_btn.config(state="normal")
        names = speakers_in(result)
        self.write("Speakers: " + ", ".join(names or ["none"]) + "\n")
        self.write(f"Transcript saved in {out}\n")
        for child in self.assign.winfo_children():
            child.destroy()
        self.speaker_vars = {}
        choices = ["(simple card)"] + [item.get("name") or item["id"] for item in self.cast]
        for i, sp in enumerate(names):
            tk.Label(self.assign, text=sp, bg="#f3ecdf").grid(row=i, column=0, sticky="w")
            var = tk.StringVar(value=choices[min(i + 1, len(choices) - 1)] if len(choices) > 1 else choices[0])
            self.speaker_vars[sp] = var
            ttk.Combobox(self.assign, textvariable=var, values=choices, width=24, state="readonly").grid(row=i, column=1)

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
        self.write("\nMatching mouths to the recording…\n")
        threading.Thread(target=self._video, daemon=True).start()

    def _video(self):
        try:
            out = Path.home() / "Desktop" / "Podcast Processor"
            out.mkdir(parents=True, exist_ok=True)
            dest = out / f"{Path(self.audio).stem}_cartoon.mp4"
            try:
                cues = build_cues(self.audio, self.result)
                self.root.after(0, lambda n=len(cues): self.write(f"Rhubarb marked {n} mouth cues.\n"))
            except Exception as exc:
                cues = None
                self.root.after(0, lambda e=exc: self.write(f"Lip sync fell back to a timer: {e}\n"))
            names = {}
            for sp, var in self.speaker_vars.items():
                picked = var.get()
                names[sp] = picked if picked != "(simple card)" else sp

            def progress(done, total):
                if done % 4 == 0:
                    self.root.after(0, lambda d=done, t=total: self.write(f"Frame {d} / {t}\n"))

            background = self._background_for_video()
            render_cartoon(self.result, self.audio, dest, names, self._cast_for_speakers(), progress, cues, background)
            self.root.after(0, lambda: self._video_done(dest))
        except Exception as exc:
            self.root.after(0, lambda: self._fail(exc))


    def _build_puppet(self, parent):
        tk.Label(parent, text="Move the mouth, then set how big this person stands.", bg="#f3ecdf").pack(anchor="w", padx=8, pady=(8, 0))
        self.preview = tk.Label(parent, bg="#f3ecdf")
        self.preview.pack(anchor="w", padx=8, pady=4)
        self.mouth_shape = tk.StringVar(value="closed")
        shapes = tk.Frame(parent, bg="#f3ecdf")
        shapes.pack(anchor="w", padx=8)
        for name in ("closed", "small", "medium", "wide", "round", "teeth"):
            tk.Radiobutton(
                shapes, text=name, value=name, variable=self.mouth_shape,
                command=self.refresh_puppet_preview, bg="#f3ecdf",
            ).pack(side="left")
        self.puppet_scale = tk.Scale(parent, label="Puppet size", from_=60, to=160, orient="horizontal", bg="#f3ecdf", command=lambda _v: self.refresh_puppet_preview())
        self.puppet_scale.set(100)
        self.puppet_scale.pack(fill="x", padx=8)
        self.mouth_x = tk.Scale(parent, label="Mouth sideways", from_=30, to=70, orient="horizontal", bg="#f3ecdf", command=lambda _v: self.refresh_puppet_preview())
        self.mouth_x.set(50)
        self.mouth_x.pack(fill="x", padx=8)
        self.mouth_y = tk.Scale(parent, label="Mouth height", from_=48, to=80, orient="horizontal", bg="#f3ecdf", command=lambda _v: self.refresh_puppet_preview())
        self.mouth_y.set(64)
        self.mouth_y.pack(fill="x", padx=8)
        self.mouth_s = tk.Scale(parent, label="Mouth size", from_=10, to=40, orient="horizontal", bg="#f3ecdf", command=lambda _v: self.refresh_puppet_preview())
        self.mouth_s.set(22)
        self.mouth_s.pack(fill="x", padx=8)
        tk.Button(parent, text="Save puppet", command=self.save_puppet).pack(anchor="w", padx=8, pady=6)

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
        tk.Label(parent, text="Pick a room, or describe one and draw it.", bg="#f3ecdf").pack(anchor="w", padx=8, pady=(8, 0))
        self.set_preview = tk.Label(parent, bg="#f3ecdf")
        self.set_preview.pack(anchor="w", padx=8, pady=4)
        row = tk.Frame(parent, bg="#f3ecdf")
        row.pack(anchor="w", padx=8)
        tk.Label(row, text="Look", bg="#f3ecdf").pack(side="left")
        self.set_preset = ttk.Combobox(row, values=PRESETS, width=16, state="readonly")
        self.set_preset.set("studio")
        self.set_preset.pack(side="left", padx=6)
        self.set_preset.bind("<<ComboboxSelected>>", lambda _e: self.refresh_set_preview())
        tk.Label(parent, text="Name", bg="#f3ecdf").pack(anchor="w", padx=8)
        self.set_name = tk.Entry(parent, width=28)
        self.set_name.pack(anchor="w", padx=8)
        tk.Label(parent, text="Describe a drawn set", bg="#f3ecdf").pack(anchor="w", padx=8)
        self.set_note = tk.Entry(parent, width=42)
        self.set_note.pack(anchor="w", padx=8, pady=2)
        buttons = tk.Frame(parent, bg="#f3ecdf")
        buttons.pack(anchor="w", padx=8, pady=4)
        tk.Button(buttons, text="Save this look", command=self.save_set).pack(side="left", padx=(0, 6))
        tk.Button(buttons, text="Draw this set", command=self.start_draw_set).pack(side="left")
        self.set_list = tk.Listbox(parent, height=4)
        self.set_list.pack(fill="x", padx=8, pady=4)
        self.set_list.bind("<<ListboxSelect>>", self.on_set_select)
        actions = tk.Frame(parent, bg="#f3ecdf")
        actions.pack(anchor="w", padx=8)
        tk.Button(actions, text="Use this set", command=self.use_selected_set).pack(side="left", padx=(0, 6))
        tk.Button(actions, text="Remove set", command=self.remove_set).pack(side="left")
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
        self.write("Drawing the set…\n")
        threading.Thread(target=self._draw_set, args=(note,), daemon=True).start()

    def _draw_set(self, note):
        try:
            blob = draw_background(note, self.xai.get().strip())
            set_id = uuid.uuid4().hex
            keep_set(set_id, self.set_name.get().strip() or "Drawn set", self.set_preset.get() or "paper", blob)
            self.root.after(0, lambda: self._set_drawn(set_id))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._fail(e))

    def _set_drawn(self, set_id):
        self._remember_set(set_id)
        self.refresh_sets()
        self._show_set(load_set(set_id))
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
        self.write(f"Video saved: {dest}\n")
        messagebox.showinfo("Video ready", f"Saved to\n{dest}")

    def _fail(self, exc):
        self.go.config(state="normal")
        self.video_btn.config(state="normal")
        self.write(f"\nError: {exc}\n")
        messagebox.showerror("Something went wrong", str(exc))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
