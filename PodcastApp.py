#!/usr/bin/env python3
"""Double-click Mac app: podcast audio to speaker cartoon video."""

import json
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

SUPPORT = Path.home() / "Library" / "Application Support" / "PodcastProcessor"
SUPPORT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(SUPPORT / "hf"))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(SUPPORT / "hf" / "hub"))
os.environ.setdefault("XDG_CACHE_HOME", str(SUPPORT / "cache"))

from podcast_processor import process_audio, speakers_in, write_summary
from podcast_video import render_cartoon

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
        root.geometry("860x720")
        root.configure(bg="#f3ecdf")
        self.audio = None
        self.result = None
        self.name_vars = {}
        cfg = load_config()

        tk.Label(
            root,
            text="Podcast to Cartoon",
            font=("Helvetica", 22, "bold"),
            bg="#f3ecdf",
            fg="#1f2a24",
        ).pack(pady=(16, 4))
        tk.Label(
            root,
            text="Separates the voices, assigns them to characters, and writes a simple hand-drawn video.",
            bg="#f3ecdf",
            fg="#3d4a43",
        ).pack()

        tk.Button(root, text="Choose audio", command=self.choose_audio).pack(pady=10)
        self.audio_label = tk.Label(root, text="No audio yet", bg="#f3ecdf")
        self.audio_label.pack()

        tk.Label(root, text="Hugging Face token", bg="#f3ecdf").pack(pady=(12, 0))
        self.token = tk.Entry(root, width=64, show="*")
        self.token.pack()
        if cfg.get("token"):
            self.token.insert(0, cfg["token"])

        row = tk.Frame(root, bg="#f3ecdf")
        row.pack(pady=10)
        tk.Label(row, text="Min speakers", bg="#f3ecdf").grid(row=0, column=0)
        self.min_sp = tk.Spinbox(row, from_=2, to=8, width=4)
        self.min_sp.delete(0, "end")
        self.min_sp.insert(0, "4")
        self.min_sp.grid(row=0, column=1, padx=(4, 16))
        tk.Label(row, text="Max speakers", bg="#f3ecdf").grid(row=0, column=2)
        self.max_sp = tk.Spinbox(row, from_=2, to=8, width=4)
        self.max_sp.delete(0, "end")
        self.max_sp.insert(0, "5")
        self.max_sp.grid(row=0, column=3, padx=4)

        self.go = tk.Button(root, text="1. Find speakers", command=self.start_process)
        self.go.pack(pady=6)

        self.assign = tk.Frame(root, bg="#f3ecdf")
        self.assign.pack(pady=6, fill="x", padx=24)

        self.video_btn = tk.Button(
            root, text="2. Make cartoon video", command=self.start_video, state="disabled"
        )
        self.video_btn.pack(pady=6)

        self.log = scrolledtext.ScrolledText(root, height=16, width=96)
        self.log.pack(padx=16, pady=12, fill="both", expand=True)
        self.write(
            "First run downloads speech models (a few GB). Leave the window open.\n"
            "Accept the pyannote model terms on huggingface.co before processing.\n"
        )

    def write(self, text):
        self.log.insert("end", text)
        self.log.see("end")

    def choose_audio(self):
        path = filedialog.askopenfilename(
            filetypes=[("Audio", "*.mp3 *.wav *.m4a *.mp4 *.aac")]
        )
        if path:
            self.audio = path
            self.audio_label.config(text=Path(path).name)

    def start_process(self):
        if not self.audio:
            messagebox.showwarning("Missing audio", "Choose an audio file first.")
            return
        token = self.token.get().strip()
        if not token:
            messagebox.showwarning("Missing token", "Paste your Hugging Face token.")
            return
        save_config({"token": token})
        os.environ["HF_TOKEN"] = token
        self.go.config(state="disabled")
        self.video_btn.config(state="disabled")
        self.write("\nFinding speakers. This can take a while...\n")
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
                language="en",
                device="cpu",
            )
            self.root.after(0, lambda: self._processed(result, out))
        except Exception as exc:
            self.root.after(0, lambda: self._failed(exc))

    def _processed(self, result, out):
        self.result = result
        self.go.config(state="normal")
        self.video_btn.config(state="normal")
        names = speakers_in(result)
        self.write("Speakers: " + ", ".join(names or ["none"]) + "\n")
        self.write(f"Transcript saved in {out}\n")
        for child in self.assign.winfo_children():
            child.destroy()
        self.name_vars = {}
        tk.Label(
            self.assign,
            text="Name each voice",
            bg="#f3ecdf",
            font=("Helvetica", 13, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        for i, sp in enumerate(names):
            tk.Label(self.assign, text=sp, bg="#f3ecdf").grid(row=i + 1, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=f"Speaker {i + 1}")
            self.name_vars[sp] = var
            tk.Entry(self.assign, textvariable=var, width=24).grid(row=i + 1, column=1, sticky="w")

    def _failed(self, exc):
        self.go.config(state="normal")
        self.write(f"\nError: {exc}\n")
        messagebox.showerror("Could not process", str(exc))

    def start_video(self):
        if not self.result:
            return
        self.video_btn.config(state="disabled")
        self.write("\nDrawing the cartoon...\n")
        names = {sp: var.get().strip() or sp for sp, var in self.name_vars.items()}
        threading.Thread(target=self._video, args=(names,), daemon=True).start()

    def _video(self, names):
        try:
            out = Path.home() / "Desktop" / "Podcast Processor"
            out.mkdir(parents=True, exist_ok=True)
            dest = out / f"{Path(self.audio).stem}_cartoon.mp4"

            def progress(done, total):
                if done % (FPS_STEP) == 0:
                    self.root.after(0, lambda d=done, t=total: self.write(f"Frame {d} / {t}\n"))

            render_cartoon(self.result, self.audio, dest, names, progress=progress)
            self.root.after(0, lambda: self._video_done(dest))
        except Exception as exc:
            self.root.after(0, lambda: self._video_failed(exc))

    def _video_done(self, dest):
        self.video_btn.config(state="normal")
        self.write(f"Video saved: {dest}\n")
        messagebox.showinfo("Video ready", f"Saved to\n{dest}")

    def _video_failed(self, exc):
        self.video_btn.config(state="normal")
        self.write(f"\nVideo error: {exc}\n")
        messagebox.showerror("Video failed", str(exc))


FPS_STEP = 4


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
