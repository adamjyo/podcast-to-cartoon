import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { drawAvatar, drawMouths } from "@/lib/draw";
import { forgetAvatar, keepAvatar, listAvatars, type SavedAvatar } from "@/lib/library";
import { HOP_MS, openness, readSpeech, shapeOnTrack } from "@/lib/audio-mouths";
import { BACKGROUNDS, defaultSpot, paintTable, SCENE_H, SCENE_W, stockCast, type HitBox, type ScenePerson, type Spot } from "@/lib/scene";
import {
  JAW,
  MOUTH_NAMES,
  STOCK_MOUTHS,
  shapeAt,
  speechLine,
  speechTimeline,
  shrinkPhoto,
  splitMouthSheet,
  type MouthName,
} from "@/lib/mouths";

export const Route = createFileRoute("/")({ component: Studio });

type Seat = {
  id: string;
  libraryId?: string;
  name: string;
  note: string;
  photo: string;
  avatar?: string;
  mouths?: Partial<Record<MouthName, string>>;
  error?: string;
  busy?: "avatar" | "mouths";
  kept?: boolean;
  mouthX: number;
  mouthY: number;
  mouthScale: number;
  on?: boolean;
  audioName?: string;
  audioUrl?: string;
  durationMs?: number;
  mouthTrack?: MouthName[];
  audioBusy?: boolean;
};

const MOUTH_SHAPES = ["closed", "small", "medium", "wide", "round", "teeth"] as const;

const MOUTH_PEOPLE = [
  { id: "adam", label: "Adam" },
  { id: "ben", label: "Ben" },
  { id: "corey", label: "Corey" },
  { id: "emily", label: "Emily" },
  { id: "abby-r", label: "Abby R" },
  { id: "abby-s", label: "Abby S" },
];

const TABLE_LAYERS = [
  { href: "/cast/layers/adam.png", file: "adam.png", label: "Adam" },
  { href: "/cast/layers/ben.png", file: "ben.png", label: "Ben" },
  { href: "/cast/layers/corey.png", file: "corey.png", label: "Corey" },
  { href: "/cast/layers/emily.png", file: "emily.png", label: "Emily" },
  { href: "/cast/layers/abby-r.png", file: "abby-r.png", label: "Abby R" },
  { href: "/cast/layers/abby-s.png", file: "abby-s.png", label: "Abby S" },
  { href: "/cast/layers/table.png", file: "table.png", label: "Table" },
];

const LINEUP_MOUTHS = [
  { href: "/cast/lineup/adam-mouths.png", file: "adam-mouths.png", label: "Adam mouths" },
  { href: "/cast/lineup/ben-mouths.png", file: "ben-mouths.png", label: "Ben mouths" },
  { href: "/cast/lineup/corey-mouths.png", file: "corey-mouths.png", label: "Corey mouths" },
  { href: "/cast/lineup/emily-mouths.png", file: "emily-mouths.png", label: "Emily mouths" },
  { href: "/cast/lineup/abby-r-mouths.png", file: "abby-r-mouths.png", label: "Abby R mouths" },
  { href: "/cast/lineup/abby-s-mouths.png", file: "abby-s-mouths.png", label: "Abby S mouths" },
];

const LINEUP = [
  { href: "/cast/lineup/adam.png", file: "adam.png", label: "Adam" },
  { href: "/cast/lineup/ben.png", file: "ben.png", label: "Ben" },
  { href: "/cast/lineup/corey.png", file: "corey.png", label: "Corey" },
  { href: "/cast/lineup/emily.png", file: "emily.png", label: "Emily" },
  { href: "/cast/lineup/abby-r.png", file: "abby-r.png", label: "Abby R" },
  { href: "/cast/lineup/abby-s.png", file: "abby-s.png", label: "Abby S" },
  { href: "/cast/lineup/table.png", file: "table.png", label: "Table" },
];

const CAST = [
  {
    name: "Adam P",
    sheets: [
      { href: "/cast/adam-p-avatar.png", file: "adam-p-avatar.png", label: "Portrait" },
      { href: "/cast/adam-p-full-body.png", file: "adam-p-full-body.png", label: "Full body" },
      { href: "/cast/adam-p-mouths.png", file: "adam-p-mouths.png", label: "Mouths" },
    ],
  },
  {
    name: "Ben",
    sheets: [
      { href: "/cast/ben-portrait.png?v=2", file: "ben-portrait.png", label: "Portrait" },
      { href: "/cast/ben-standing.png?v=2", file: "ben-standing.png", label: "Standing" },
      { href: "/cast/ben-mouths.png?v=2", file: "ben-mouths.png", label: "Mouths" },
      { href: "/cast/ben-sitting.png?v=2", file: "ben-sitting.png", label: "Sitting" },
      { href: "/cast/ben-at-table.png?v=2", file: "ben-at-table.png", label: "At the table" },
    ],
  },
  {
    name: "Corey",
    sheets: [
      { href: "/cast/corey-portrait.png", file: "corey-portrait.png", label: "Portrait" },
      { href: "/cast/corey-full-body.png", file: "corey-full-body.png", label: "Full body" },
      { href: "/cast/corey-mouths.png", file: "corey-mouths.png", label: "Mouths" },
      { href: "/cast/corey-sitting.png", file: "corey-sitting.png", label: "Sitting" },
    ],
  },
  {
    name: "Emily",
    sheets: [
      { href: "/cast/emily-portrait.png", file: "emily-portrait.png", label: "Portrait" },
      { href: "/cast/emily-full-body.png", file: "emily-full-body.png", label: "Full body" },
      { href: "/cast/emily-mouths.png", file: "emily-mouths.png", label: "Mouths" },
      { href: "/cast/emily-sitting.png", file: "emily-sitting.png", label: "Sitting" },
    ],
  },
  {
    name: "Abby R",
    sheets: [
      { href: "/cast/abby-r-portrait.png", file: "abby-r-portrait.png", label: "Portrait" },
      { href: "/cast/abby-r-full-body.png", file: "abby-r-full-body.png", label: "Full body" },
      { href: "/cast/abby-r-mouths.png", file: "abby-r-mouths.png", label: "Mouths" },
      { href: "/cast/abby-r-sitting.png", file: "abby-r-sitting.png", label: "Sitting" },
    ],
  },
  {
    name: "Abby S",
    sheets: [
      { href: "/cast/abby-s-portrait.png", file: "abby-s-portrait.png", label: "Portrait" },
      { href: "/cast/abby-s-full-body.png", file: "abby-s-full-body.png", label: "Full body" },
      { href: "/cast/abby-s-mouths.png", file: "abby-s-mouths.png", label: "Mouths" },
      { href: "/cast/abby-s-sitting.png", file: "abby-s-sitting.png", label: "Sitting" },
    ],
  },
];

export function Studio() {
  const [seats, setSeats] = useState<Seat[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [shape, setShape] = useState<MouthName>("closed");
  const [playing, setPlaying] = useState(false);
  const [playMs, setPlayMs] = useState(0);
  const [clipUrl, setClipUrl] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportNote, setExportNote] = useState<string | null>(null);
  const [library, setLibrary] = useState<SavedAvatar[]>([]);
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const [background, setBackground] = useState("coffee");
  const [spots, setSpots] = useState<Record<string, Spot>>({});
  const [room, setRoom] = useState({ x: 50, y: 50, scale: 100 });
  const [editLayer, setEditLayer] = useState<"background" | "foreground">("background");
  const [fgId, setFgId] = useState("none");
  const [fgPlace, setFgPlace] = useState({ x: 50, y: 62, scale: 46 });
  const [fgItems, setFgItems] = useState<{ id: string; label: string; href: string }[]>([]);
  const [bgItems, setBgItems] = useState<{ id: string; label: string; href: string; x: number; y: number; scale: number }[]>(
    () => BACKGROUNDS.map((item) => ({ id: item.id, label: item.label, href: item.href, x: 50, y: 50, scale: 100 })),
  );
  const [selected, setSelected] = useState<{ id: string; kind: HitBox["kind"] }>({
    id: "background",
    kind: "background",
  });
  const [castOn, setCastOn] = useState<Record<string, boolean>>({});
  const [layoutReady, setLayoutReady] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const fgFileRef = useRef<HTMLInputElement>(null);
  const bgFileRef = useRef<HTMLInputElement>(null);
  const sceneRef = useRef<HTMLCanvasElement>(null);
  const boxesRef = useRef<HitBox[]>([]);
  const dragRef = useRef<{
    id: string;
    kind: HitBox["kind"];
    mode: "move" | "resize";
    x: number;
    y: number;
    origin: Spot | { x: number; y: number; scale: number };
  } | null>(null);
  const playMsRef = useRef(0);
  const audioRefs = useRef<Record<string, HTMLAudioElement | null>>({});
  const line = useMemo(() => speechTimeline(2), []);
  const duration = useMemo(() => {
    const heard = seats.filter((item) => item.on !== false);
    return heard.reduce((max, item) => Math.max(max, item.durationMs ?? 0), 0) || line.duration;
  }, [seats, line.duration]);
  const durationRef = useRef(duration);
  durationRef.current = duration;
  const usingAudio = seats.some((item) => item.on !== false && (item.mouthTrack?.length ?? 0) > 0);

  function personOn(id: string) {
    if (seats.length) return seats.find((item) => item.id === id)?.on !== false;
    return castOn[id] !== false;
  }

  function shapeFor(item: Seat | undefined, ms: number): MouthName {
    if (item?.mouthTrack?.length) return shapeOnTrack(item.mouthTrack, ms);
    return shapeAt(ms);
  }

  function loudestAt(ms: number): Seat | undefined {
    const voiced = seats.filter((item) => item.on !== false && item.mouthTrack?.length);
    if (!voiced.length) return seat;
    return voiced.reduce((best, item) =>
      openness(shapeFor(item, ms)) > openness(shapeFor(best, ms)) ? item : best,
    );
  }

  const seat = seats.find((s) => s.id === active) ?? seats[0];

  useEffect(() => {
    void listAvatars()
      .then(setLibrary)
      .catch(() => setLibraryError("Saved avatars are unavailable in this browser."));
  }, []);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("paper-mic-layout");
      if (raw) {
        const parsed = JSON.parse(raw) as { spots?: Record<string, Spot>; room?: { x: number; y: number; scale: number } };
        if (parsed.spots) setSpots(parsed.spots);
        if (parsed.room) setRoom(parsed.room);
      }
    } catch {
      // A bad saved layout should not block the scene.
    }
    setLayoutReady(true);
  }, []);

  useEffect(() => {
    if (!layoutReady) return;
    localStorage.setItem("paper-mic-layout", JSON.stringify({ spots, room }));
  }, [spots, room, layoutReady]);

  const applyPlayhead = (ms: number) => {
    const who = loudestAt(ms);
    if (who?.mouthTrack?.length) {
      setShape(shapeFor(who, ms));
      setActive((current) => (current === who.id ? current : who.id));
      return;
    }
    setShape(ms >= durationRef.current ? "closed" : shapeAt(ms));
  };
  const applyRef = useRef(applyPlayhead);
  applyRef.current = applyPlayhead;

  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    let last = performance.now();
    const step = (now: number) => {
      const next = playMsRef.current + (now - last);
      last = now;
      if (next >= durationRef.current) {
        playMsRef.current = durationRef.current;
        setPlayMs(durationRef.current);
        setShape("closed");
        setPlaying(false);
        return;
      }
      playMsRef.current = next;
      setPlayMs(next);
      applyRef.current(next);
      frame = window.requestAnimationFrame(step);
    };
    frame = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(frame);
  }, [playing]);

  useEffect(() => {
    for (const item of seats) {
      const el = audioRefs.current[item.id];
      if (!el) continue;
      if (playing && item.on !== false) {
        if (Math.abs(el.currentTime * 1000 - playMsRef.current) > 200) {
          el.currentTime = playMsRef.current / 1000;
        }
        void el.play().catch(() => undefined);
      } else {
        el.pause();
      }
    }
  }, [playing, seats]);

  function seek(ms: number) {
    const next = Math.max(0, Math.min(durationRef.current, ms));
    playMsRef.current = next;
    setPlayMs(next);
    for (const el of Object.values(audioRefs.current)) {
      if (el && Math.abs(el.currentTime * 1000 - next) > 40) el.currentTime = next / 1000;
    }
    applyRef.current(next);
  }

  function togglePlay() {
    if (playMsRef.current >= durationRef.current - 30) seek(0);
    setPlaying((on) => !on);
  }

  function clock(ms: number) {
    const total = Math.max(0, Math.round(ms / 100) / 10);
    const mins = Math.floor(total / 60);
    const secs = (total % 60).toFixed(1).padStart(4, "0");
    return `${mins}:${secs}`;
  }

  async function onFiles(list: FileList | null) {
    if (!list?.length) return;
    const room = 5 - seats.length;
    const files = Array.from(list).slice(0, room);
    const next: Seat[] = [];
    for (const file of files) {
      if (!file.type.startsWith("image/")) continue;
      const photo = await shrinkPhoto(file);
      next.push({
        id: crypto.randomUUID(),
        name: file.name.replace(/\.[^.]+$/, "").replace(/[-_]/g, " "),
        note: "",
        photo,
        mouthX: 50,
        mouthY: 42,
        mouthScale: 16,
      });
    }
    setSeats((prev) => [...prev, ...next].slice(0, 5));
    setActive((current) => current ?? next[0]?.id ?? null);
  }

  function patch(id: string, partial: Partial<Seat>) {
    setSeats((prev) => prev.map((s) => (s.id === id ? { ...s, ...partial } : s)));
  }

  async function attachAudio(id: string, file: File | undefined) {
    if (!file) return;
    patch(id, { audioBusy: true, error: undefined });
    try {
      const speech = await readSpeech(file);
      setSeats((prev) =>
        prev.map((item) => {
          if (item.id !== id) return item;
          if (item.audioUrl) URL.revokeObjectURL(item.audioUrl);
          return {
            ...item,
            audioBusy: false,
            audioName: file.name,
            audioUrl: speech.url,
            durationMs: speech.durationMs,
            mouthTrack: speech.track,
            error: undefined,
          };
        }),
      );
      setActive(id);
      seek(0);
      setExportNote(`${file.name} sets the mouth. The bar covers ${clock(speech.durationMs)}.`);
    } catch (err) {
      patch(id, {
        audioBusy: false,
        error: err instanceof Error ? err.message : "Could not read that audio.",
      });
    }
  }

  async function develop(id: string) {
    const current = seats.find((s) => s.id === id);
    if (!current || current.busy) return;
    patch(id, { busy: "avatar", error: undefined });
    const result = await drawAvatar({
      data: { imageDataUrl: current.photo, note: current.note },
    });
    if (!result.ok) {
      patch(id, { busy: undefined, error: result.error });
      return;
    }
    patch(id, { busy: undefined, avatar: result.image, kept: false, error: undefined });
    setActive(id);
  }

  async function cutMouths(id: string) {
    const current = seats.find((s) => s.id === id);
    if (!current?.avatar || current.busy) return;
    patch(id, { busy: "mouths", error: undefined });
    const result = await drawMouths({ data: { imageDataUrl: current.avatar } });
    if (!result.ok) {
      patch(id, { busy: undefined, error: result.error });
      return;
    }
    try {
      const mouths = await splitMouthSheet(result.image);
      patch(id, { busy: undefined, mouths, kept: false, error: undefined });
    } catch (err) {
      patch(id, {
        busy: undefined,
        error: err instanceof Error ? err.message : "Could not cut the mouths.",
      });
    }
  }

  async function keep(id: string) {
    const current = seats.find((s) => s.id === id);
    if (!current?.avatar) return;
    const libraryId = current.libraryId ?? crypto.randomUUID();
    const spot = spotFor(id);
    try {
      await keepAvatar({
        id: libraryId,
        name: current.name || "Unnamed",
        note: current.note,
        photo: current.photo,
        avatar: current.avatar,
        mouths: current.mouths,
        mouthX: spot.mouthX,
        mouthY: spot.mouthY,
        mouthScale: spot.mouthScale,
        sceneX: spot.x,
        sceneY: spot.y,
        sceneScale: spot.scale,
        savedAt: Date.now(),
      });
      patch(id, {
        libraryId,
        kept: true,
        mouthX: spot.mouthX,
        mouthY: spot.mouthY,
        mouthScale: spot.mouthScale,
        error: undefined,
      });
      setSpots((prev) => ({ ...prev, [id]: spot }));
      setLibrary(await listAvatars());
      setExportNote(`Mouth placement saved for ${current.name || "this person"}.`);
    } catch (err) {
      patch(id, {
        error: err instanceof Error ? err.message : "Could not save that avatar.",
      });
    }
  }

  function loadImage(src: string) {
    return new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("Could not load a picture for the video."));
      img.src = src;
    });
  }

  const imageCache = useRef(new Map<string, Promise<HTMLImageElement>>());
  const paintGen = useRef(0);

  function loadCached(src: string) {
    let pending = imageCache.current.get(src);
    if (!pending) {
      pending = loadImage(src);
      imageCache.current.set(src, pending);
    }
    return pending;
  }

  async function drawScene(canvas: HTMLCanvasElement, ms: number, sample: MouthName, gen?: number) {
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const everyone: { person: ScenePerson; shape: MouthName }[] = seats.length
      ? seats.map((item) => ({
          person: {
            id: item.id,
            name: item.name,
            body: item.avatar ?? item.photo,
            mouths: item.mouths ?? {},
            mouthX: item.mouthX,
            mouthY: item.mouthY,
            mouthScale: item.mouthScale,
          },
          shape: item.mouthTrack?.length ? shapeOnTrack(item.mouthTrack, ms) : usingAudio ? "closed" : sample,
        }))
      : stockCast().map((person) => ({
          person,
          shape: sample,
        }));
    const roster = everyone.filter((entry) => personOn(entry.person.id));
    const bg = bgItems.find((item) => item.id === background) ?? bgItems[0];
    const backgroundImg = await loadCached(bg?.href ?? BACKGROUNDS[0].href);
    const painted = [];
    for (let index = 0; index < roster.length; index += 1) {
      const entry = roster[index];
      if (!entry) continue;
      const fullIndex = Math.max(0, everyone.findIndex((item) => item.person.id === entry.person.id));
      const spot = spots[entry.person.id] ?? defaultSpot(fullIndex, everyone.length, entry.person);
      const mouthSrc = entry.person.mouths[entry.shape] ?? STOCK_MOUTHS[entry.shape];
      painted.push({
        ...entry,
        spot,
        body: await loadCached(entry.person.body),
        mouth: await loadCached(mouthSrc),
      });
    }
    if (gen !== undefined && gen !== paintGen.current) return;
    const fg = fgItems.find((item) => item.id === fgId);
    const foreground = fg ? { image: await loadCached(fg.href), place: fgPlace } : null;
    if (gen !== undefined && gen !== paintGen.current) return;
    boxesRef.current = paintTable(ctx, backgroundImg, painted, room, selected, editLayer, foreground);
  }

  function paintFrame(
    ctx: CanvasRenderingContext2D,
    avatar: HTMLImageElement,
    mouth: HTMLImageElement,
    place: { mouthX: number; mouthY: number; mouthScale: number },
    shapeName: MouthName,
  ) {
    const w = ctx.canvas.width;
    const h = ctx.canvas.height;
    ctx.fillStyle = "#f3ecdf";
    ctx.fillRect(0, 0, w, h);
    const cover = Math.max(w / avatar.width, h / avatar.height);
    const dw = avatar.width * cover;
    const dh = avatar.height * cover;
    const jaw = JAW[shapeName];
    const bob = (jaw - 1) * 6;
    ctx.drawImage(avatar, (w - dw) / 2, (h - dh) / 2 + bob, dw, dh);
    const mw = (place.mouthScale / 100) * w;
    const mh = mouth.width ? (mouth.height / mouth.width) * mw * jaw : mw * jaw;
    const x = (place.mouthX / 100) * w - mw / 2;
    const y = (place.mouthY / 100) * h;
    ctx.drawImage(mouth, x, y, mw, mh);
  }

  async function exportVideo() {
    const voiced = seats.filter((item) => item.on !== false && item.mouthTrack?.length && item.audioUrl && item.durationMs);
    const mimeType = (
      voiced.length
        ? ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm", "video/mp4"]
        : ["video/webm;codecs=vp9", "video/webm", "video/mp4"]
    ).find((type) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(type));
    if (!mimeType) {
      setExportNote("This browser cannot record a video.");
      return;
    }
    setExporting(true);
    setPlaying(false);
    setExportNote(voiced.length ? "Recording the audio…" : "Drawing the line…");
    let audioCtx: AudioContext | null = null;
    try {
      const canvas = document.createElement("canvas");
      canvas.width = SCENE_W;
      canvas.height = SCENE_H;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Could not start the video.");
      await drawScene(canvas, 0, "closed");
      const canvasStream = canvas.captureStream(24);
      let recordStream: MediaStream = canvasStream;
      if (voiced.length) {
        audioCtx = new AudioContext();
        const dest = audioCtx.createMediaStreamDestination();
        for (const person of voiced) {
          const bytes = await (await fetch(person.audioUrl!)).arrayBuffer();
          const buffer = await audioCtx.decodeAudioData(bytes);
          const source = audioCtx.createBufferSource();
          source.buffer = buffer;
          source.connect(dest);
          source.start();
        }
        recordStream = new MediaStream([
          ...canvasStream.getVideoTracks(),
          ...dest.stream.getAudioTracks(),
        ]);
      }
      const rec = new MediaRecorder(recordStream, { mimeType, videoBitsPerSecond: 2_500_000 });
      const chunks: Blob[] = [];
      rec.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      const stopped = new Promise<void>((resolve) => {
        rec.onstop = () => resolve();
      });
      rec.start();
      if (voiced.length) {
        const total = Math.max(...voiced.map((item) => item.durationMs ?? 0));
        const steps = Math.max(1, Math.ceil(total / HOP_MS));
        for (let i = 0; i < steps; i += 1) {
          await drawScene(canvas, i * HOP_MS, "closed");
          if (i % 10 === 0) setExportNote(`Exporting the table… ${Math.round(((i + 1) / steps) * 100)}%`);
          await new Promise((resolve) => window.setTimeout(resolve, HOP_MS));
        }
      } else {
        const beats = speechLine(2);
        for (let i = 0; i < beats.length; i += 1) {
          const beat = beats[i];
          if (!beat) continue;
          setShape(beat.shape);
          await drawScene(canvas, 0, beat.shape);
          setExportNote(`Exporting the table… ${Math.round(((i + 1) / beats.length) * 100)}%`);
          await new Promise((resolve) => window.setTimeout(resolve, beat.ms));
        }
      }
      await drawScene(canvas, 0, "closed");
      await new Promise((resolve) => window.setTimeout(resolve, 80));
      rec.stop();
      await stopped;
      const blob = new Blob(chunks, { type: mimeType });
      const url = URL.createObjectURL(blob);
      setClipUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return url;
      });
      const link = document.createElement("a");
      link.href = url;
      link.download = `${(seat?.name || "paper-mic").replace(/\s+/g, "-").toLowerCase()}.${mimeType.includes("mp4") ? "mp4" : "webm"}`;
      link.click();
      setShape("closed");
      setExportNote("Video downloaded.");
    } catch (err) {
      setExportNote(err instanceof Error ? err.message : "Could not export the video.");
    } finally {
      void audioCtx?.close();
      setExporting(false);
    }
  }

  function reuse(saved: SavedAvatar) {
    const existing = seats.find((s) => s.libraryId === saved.id);
    if (existing) {
      setActive(existing.id);
      return;
    }
    if (seats.length >= 5) return;
    const next: Seat = {
      id: crypto.randomUUID(),
      libraryId: saved.id,
      name: saved.name,
      note: saved.note,
      photo: saved.photo,
      avatar: saved.avatar,
      mouths: saved.mouths,
      kept: true,
      mouthX: saved.mouthX,
      mouthY: saved.mouthY,
      mouthScale: saved.mouthScale,
    };
    const base = defaultSpot(seats.length, seats.length + 1, {
      id: next.id,
      name: next.name,
      body: next.avatar ?? next.photo,
      mouths: next.mouths ?? {},
      mouthX: next.mouthX,
      mouthY: next.mouthY,
      mouthScale: next.mouthScale,
    });
    const spot: Spot = {
      ...base,
      mouthX: saved.mouthX,
      mouthY: saved.mouthY,
      mouthScale: saved.mouthScale,
      ...(saved.sceneX === undefined ? {} : { x: saved.sceneX }),
      ...(saved.sceneY === undefined ? {} : { y: saved.sceneY }),
      ...(saved.sceneScale === undefined ? {} : { scale: saved.sceneScale }),
    };
    setSpots((prev) => ({ ...prev, [next.id]: spot }));
    setSeats((prev) => [...prev, next]);
    setActive(next.id);
  }

  async function forget(id: string) {
    await forgetAvatar(id);
    setLibrary(await listAvatars());
    setSeats((prev) => prev.map((s) => (s.libraryId === id ? { ...s, kept: false, libraryId: undefined } : s)));
  }

  const mouths = seat?.mouths ?? STOCK_MOUTHS;
  const mouthSrc = mouths[shape] ?? STOCK_MOUTHS[shape];

  useEffect(() => {
    const canvas = sceneRef.current;
    if (!canvas) return;
    const gen = ++paintGen.current;
    let cancel = false;
    void drawScene(canvas, playMs, shape, gen).catch(() => {
      if (!cancel) setExportNote("Could not draw the table.");
    });
    return () => {
      cancel = true;
    };
  }, [playMs, shape, seats, background, usingAudio, spots, room, selected, castOn, editLayer, fgId, fgItems, fgPlace, bgItems]);

  function togglePerson(id: string) {
    const item = seats.find((seatItem) => seatItem.id === id);
    if (item) {
      patch(id, { on: item.on === false });
      return;
    }
    setCastOn((prev) => ({ ...prev, [id]: prev[id] === false }));
  }

  function spotFor(id: string): Spot {
    const saved = spots[id];
    if (saved) return saved;
    const roster: ScenePerson[] = seats.length
      ? seats.map((item) => ({
          id: item.id,
          name: item.name,
          body: item.photo,
          mouths: item.mouths ?? {},
          mouthX: item.mouthX,
          mouthY: item.mouthY,
          mouthScale: item.mouthScale,
        }))
      : stockCast();
    const index = Math.max(0, roster.findIndex((item) => item.id === id));
    return defaultSpot(index, roster.length, roster[index] ?? roster[0]!);
  }

  function scenePoint(event: PointerEvent<HTMLCanvasElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * SCENE_W,
      y: ((event.clientY - rect.top) / rect.height) * SCENE_H,
    };
  }

  function pickBox(x: number, y: number): HitBox | null {
    const inside = (box: HitBox) => x >= box.x && y >= box.y && x <= box.x + box.w && y <= box.y + box.h;
    const boxes = boxesRef.current;
    return (
      boxes.find((box) => box.role === "handle" && inside(box)) ??
      [...boxes].reverse().find((box) => box.kind === "mouth" && box.role === "body" && inside(box)) ??
      [...boxes].reverse().find((box) => box.kind === "person" && box.role === "body" && inside(box)) ??
      null
    );
  }

  function onSceneDown(event: PointerEvent<HTMLCanvasElement>) {
    const point = scenePoint(event);
    const box = pickBox(point.x, point.y);
    if (editLayer === "foreground") {
      if (fgId === "none") return;
      setSelected({ id: "foreground", kind: "foreground" });
      dragRef.current = {
        id: "foreground",
        kind: "foreground",
        mode: box?.role === "handle" ? "resize" : "move",
        x: point.x,
        y: point.y,
        origin: { ...fgPlace },
      };
      event.currentTarget.setPointerCapture(event.pointerId);
      return;
    }
    setSelected({ id: "background", kind: "background" });
    dragRef.current = {
      id: "background",
      kind: "background",
      mode: box?.role === "handle" ? "resize" : "move",
      x: point.x,
      y: point.y,
      origin: { ...room },
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onSceneMove(event: PointerEvent<HTMLCanvasElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    const point = scenePoint(event);
    const dx = ((point.x - drag.x) / SCENE_W) * 100;
    const dy = ((point.y - drag.y) / SCENE_H) * 100;
    const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
    const origin = drag.origin as { x: number; y: number; scale: number };
    const next =
      drag.mode === "resize"
        ? { ...origin, scale: clamp(origin.scale + dx, drag.kind === "foreground" ? 8 : 40, drag.kind === "foreground" ? 180 : 250) }
        : { ...origin, x: origin.x + dx, y: origin.y + dy };
    if (drag.kind === "foreground") setFgPlace(next);
    else setRoom(next);
  }

  function onSceneUp() {
    const drag = dragRef.current;
    dragRef.current = null;
    if (!drag || drag.kind === "background") return;
    const item = seats.find((seatItem) => seatItem.id === drag.id);
    if (item?.avatar && item.libraryId) void keep(item.id);
  }

  function activateLayer(layer: "background" | "foreground") {
    setEditLayer(layer);
    setSelected(layer === "background" ? { id: "background", kind: "background" } : { id: "foreground", kind: "foreground" });
  }

  function chooseBackground(id: string) {
    const chosen = bgItems.find((item) => item.id === id);
    setBgItems((prev) => prev.map((item) => (item.id === background ? { ...item, x: room.x, y: room.y, scale: room.scale } : item)));
    if (chosen) setRoom({ x: chosen.x, y: chosen.y, scale: chosen.scale });
    setBackground(id);
    activateLayer("background");
  }

  function addLayerFile(layer: "background" | "foreground", file: File | undefined) {
    if (!file) return;
    const item = {
      id: crypto.randomUUID(),
      label: file.name.replace(/\.[^.]+$/, "") || "New",
      href: URL.createObjectURL(file),
      x: 50,
      y: layer === "foreground" ? 62 : 50,
      scale: layer === "foreground" ? 46 : 100,
    };
    if (layer === "foreground") {
      setFgItems((prev) => [...prev, item]);
      setFgId(item.id);
      setFgPlace({ x: item.x, y: item.y, scale: item.scale });
      activateLayer("foreground");
      return;
    }
    setBgItems((prev) => [...prev, item]);
    setRoom({ x: item.x, y: item.y, scale: item.scale });
    setBackground(item.id);
    activateLayer("background");
  }

  function jump(id: string) {
    const root = document.getElementById("options-scroll");
    const target = document.getElementById(id);
    if (!root || !target) return;
    const top = target.getBoundingClientRect().top - root.getBoundingClientRect().top + root.scrollTop - 56;
    root.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
  }

  const jumps = [
    ["mouths", "Mouths"],
    ["backgrounds", "Backgrounds"],
    ["table", "Table"],
    ["lineup", "Lineup"],
    ["portraits", "Portraits"],
    ["stage", "Stage"],
  ] as const;

  return (
    <div className="flex h-full min-h-0 w-full">
      <section className="flex h-full min-w-0 flex-col gap-3 overflow-y-auto p-3" style={{ width: "75%" }}>
        <canvas
          ref={sceneRef}
          width={SCENE_W}
          height={SCENE_H}
          onPointerDown={onSceneDown}
          onPointerMove={onSceneMove}
          onPointerUp={onSceneUp}
          onPointerCancel={onSceneUp}
          className="aspect-video w-full shrink-0 cursor-grab touch-none rounded-3xl bg-ink"
        />
        <div className={`rounded-2xl border p-3 ${editLayer === "foreground" ? "border-sienna bg-cream" : "border-line bg-paper"}`}>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => activateLayer("foreground")} className="h-11 rounded-full bg-ink px-4 text-sm font-medium text-cream">
              Foreground
            </button>
            <select
              aria-label="Foreground elements"
              value={fgId}
              onChange={(event) => {
                setFgId(event.target.value);
                activateLayer("foreground");
              }}
              className="h-11 min-w-40 flex-1 rounded-xl border border-line bg-cream px-3 text-sm text-ink"
            >
              <option value="none">None</option>
              {fgItems.map((item) => (
                <option key={item.id} value={item.id}>{item.label}</option>
              ))}
            </select>
            <button type="button" onClick={() => fgFileRef.current?.click()} className="h-11 rounded-full border border-line bg-cream px-4 text-sm font-medium text-ink">
              Add new
            </button>
          </div>
          <p className="mt-2 text-sm text-muted">
            {editLayer === "foreground" ? "Foreground is the only thing you can move." : "Click Foreground to edit only this layer."}
          </p>
        </div>
        <div className={`rounded-2xl border p-3 ${editLayer === "background" ? "border-sienna bg-cream" : "border-line bg-paper"}`}>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => activateLayer("background")} className="h-11 rounded-full bg-ink px-4 text-sm font-medium text-cream">
              Background
            </button>
            <select
              aria-label="Background elements"
              value={background}
              onChange={(event) => chooseBackground(event.target.value)}
              className="h-11 min-w-40 flex-1 rounded-xl border border-line bg-cream px-3 text-sm text-ink"
            >
              {bgItems.map((item) => (
                <option key={item.id} value={item.id}>{item.label}</option>
              ))}
            </select>
            <button type="button" onClick={() => bgFileRef.current?.click()} className="h-11 rounded-full border border-line bg-cream px-4 text-sm font-medium text-ink">
              Add new
            </button>
          </div>
          <p className="mt-2 text-sm text-muted">
            {editLayer === "background" ? "Background is the only thing you can move. Drag to slide it, drag the orange corner to resize." : "Click Background to edit only this layer."}
          </p>
        </div>
        <input ref={fgFileRef} type="file" accept="image/*" className="sr-only" onChange={(event) => { addLayerFile("foreground", event.target.files?.[0]); event.target.value = ""; }} />
        <input ref={bgFileRef} type="file" accept="image/*" className="sr-only" onChange={(event) => { addLayerFile("background", event.target.files?.[0]); event.target.value = ""; }} />
      </section>
      <aside id="options-scroll" className="h-full min-w-0 overflow-y-auto border-l border-line bg-paper p-3" style={{ width: "25%" }}>
    <main className="mx-auto min-h-full max-w-6xl px-4 py-8 pb-56 sm:px-6">
      <nav className="sticky top-0 z-30 -mx-4 mb-6 flex gap-2 overflow-x-auto border-b border-line bg-paper px-4 py-2 sm:-mx-6 sm:px-6">
        {jumps.map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => jump(id)}
            className="h-11 shrink-0 rounded-full border border-line bg-cream px-4 text-sm font-medium text-ink"
          >
            {label}
          </button>
        ))}
        <button
          type="button"
          className="h-11 shrink-0 rounded-full bg-sienna px-4 text-sm font-medium text-cream disabled:opacity-40"
          disabled={exporting}
          onClick={() => void exportVideo()}
        >
          {exporting ? "Exporting…" : "Export"}
        </button>
      </nav>
      <section className="mb-8 rounded-3xl border border-line bg-cream p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium tracking-wide text-sienna">Download</p>
            <h2 className="font-display text-3xl text-ink">Daily streams</h2>
            <p className="mt-1 text-sm text-muted">16 Oct 2025 through 14 Oct 2026. 364 days.</p>
          </div>
          <a
            href="/distrokid-daily-streams.csv"
            download="distrokid-daily-streams.csv"
            className="inline-flex h-12 items-center justify-center rounded-full bg-sienna px-5 font-medium text-cream"
          >
            Download CSV
          </a>
        </div>
        <div className="mt-6 border-t border-line pt-5">
          <h3 className="font-display text-2xl text-ink">Changelog</h3>
          <ol className="mt-3 flex flex-col gap-3 text-sm text-ink">
            <li>
              <span className="font-medium">Live switcher.</span>{" "}
              <span className="text-muted">Wide shows the whole table. Each name is a close-up. Click one while it plays to cut, then export that show as an MP4.</span>
            </li>
            <li>
              <span className="font-medium">The table.</span>{" "}
              <span className="text-muted">People sit behind one table. Turning someone off leaves them out of the video. Their mouth and seat are saved on the avatar.</span>
            </li>
            <li>
              <span className="font-medium">Mouths.</span>{" "}
              <span className="text-muted">Each person’s mouth pictures line up on their face, and each voice drives its own mouth.</span>
            </li>
          </ol>
          <a
            href="https://github.com/adamjyo/podcast-to-cartoon/actions"
            className="mt-4 inline-flex h-11 items-center text-sm font-medium text-sienna"
          >
            Download the Mac app from GitHub
          </a>
        </div>
      </section>
      <header className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium tracking-wide text-sienna">Paper Mic</p>
          <h1 className="font-display text-4xl text-balance text-ink sm:text-5xl">
            The table
          </h1>
          <p className="mt-2 max-w-xl text-pretty text-muted">
            Turn people on or off, drag them into place, and play. Mouths follow each person’s audio.
          </p>
        </div>
        <button
          type="button"
          className="h-12 rounded-full bg-sienna px-5 font-medium text-cream disabled:opacity-40"
          onClick={() => inputRef.current?.click()}
          disabled={seats.length >= 5}
        >
          {seats.length ? "Add another headshot" : "Load headshots"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          className="sr-only"
          onChange={(e) => {
            void onFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </header>

      <div id="stage" className="jump-target">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <h2 className="mr-2 font-display text-2xl text-ink">The table</h2>
          {BACKGROUNDS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setBackground(item.id)}
              className={`h-11 rounded-full px-4 text-sm font-medium ${
                background === item.id ? "bg-ink text-cream" : "border border-line bg-cream text-ink"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="mb-3 flex flex-wrap gap-2">
          {(seats.length
            ? seats.map((item) => ({ id: item.id, name: item.name || "Person", on: item.on !== false }))
            : stockCast().map((item) => ({
                id: item.id,
                name: MOUTH_PEOPLE.find((person) => person.id === item.id)?.label ?? item.name,
                on: castOn[item.id] !== false,
              }))
          ).map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={item.on}
              onClick={() => togglePerson(item.id)}
              className={`h-11 rounded-full px-4 text-sm font-medium ${
                item.on ? "bg-ink text-cream" : "border border-line bg-cream text-muted line-through"
              }`}
            >
              {item.name} {item.on ? "On" : "Off"}
            </button>
          ))}
        </div>
        <p className="mt-2 mb-6 text-sm text-muted">
          The picture on the left is the scene. Use Foreground or Background under it to choose what you can move.
        </p>
      {seats.length === 0 ? (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="flex min-h-72 w-full flex-col items-center justify-center rounded-3xl border border-dashed border-line bg-cream px-6 text-center"
        >
          <span className="font-display text-2xl text-ink">Drop photos here</span>
          <span className="mt-2 max-w-sm text-muted">
            Up to five people. A clear face, looking at the camera, works best.
          </span>
        </button>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <section className="rounded-3xl border border-line bg-cream p-4 sm:p-6">
            {seat?.avatar ? (
              <div className="relative mx-auto aspect-portrait w-full max-w-md overflow-hidden rounded-2xl bg-paper">
                <img loading="lazy" src={seat.avatar} alt="" className="h-full w-full object-cover" />
                <img loading="lazy"
                  src={mouthSrc}
                  alt=""
                  className="pointer-events-none absolute -translate-x-1/2"
                  style={{
                    left: `${seat.mouthX}%`,
                    top: `${seat.mouthY}%`,
                    width: `${seat.mouthScale}%`,
                    transformOrigin: "center 18%",
                    transform: `translateX(-50%) scaleY(${playing || exporting || playMs > 0 ? JAW[shape] : 1})`,
                  }}
                />
              </div>
            ) : (
              <div className="relative mx-auto aspect-portrait w-full max-w-md overflow-hidden rounded-2xl bg-paper">
                <img loading="lazy"
                  src={seat?.photo}
                  alt=""
                  className="h-full w-full object-cover grayscale-[0.2]"
                />
                <p className="absolute inset-x-0 bottom-0 bg-ink/80 px-4 py-3 text-center text-cream">
                  Headshot loaded. Draw the avatar to start.
                </p>
              </div>
            )}

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button
                type="button"
                className="h-11 rounded-full bg-ink px-4 text-cream disabled:opacity-40"
                disabled={!seat || playing || exporting}
                onClick={togglePlay}
              >
                {playing ? "Pause" : "Play"}
              </button>
              <button
                type="button"
                className="h-11 rounded-full bg-sienna px-4 font-medium text-cream disabled:opacity-40"
                disabled={exporting}
                onClick={() => void exportVideo()}
              >
                {exporting ? "Exporting…" : "Export video"}
              </button>
              <div className="flex gap-2">
                {MOUTH_NAMES.map((name) => (
                  <button
                    key={name}
                    type="button"
                    aria-label={name}
                    onClick={() => {
                      setPlaying(false);
                      seek(0);
                      setShape(name);
                    }}
                    className={`h-11 w-11 overflow-hidden rounded-full border ${
                      shape === name ? "border-sienna" : "border-line"
                    } bg-paper`}
                  >
                    <img loading="lazy" src={(seat?.mouths ?? STOCK_MOUTHS)[name]} alt="" className="h-full w-full object-contain" />
                  </button>
                ))}
              </div>
            </div>
          </section>

          <aside className="flex flex-col gap-3">
            {seats.map((item) => (
              <article
                key={item.id}
                className={`rounded-2xl border bg-cream p-3 ${
                  item.id === seat?.id ? "border-sienna" : "border-line"
                }`}
              >
                <button type="button" className="flex w-full gap-3 text-left" onClick={() => setActive(item.id)}>
                  <img loading="lazy" src={item.avatar ?? item.photo} alt="" className="h-16 w-14 rounded-xl object-cover" />
                  <span className="min-w-0 flex-1">
                    <input
                      value={item.name}
                      onChange={(e) => patch(item.id, { name: e.target.value })}
                      onClick={(e) => e.stopPropagation()}
                      className="w-full bg-transparent font-medium text-ink outline-none"
                      aria-label="Name"
                    />
                    <span className="block text-sm text-muted">
                      {item.busy === "avatar"
                        ? "Drawing…"
                        : item.busy === "mouths"
                          ? "Cutting mouths…"
                          : item.avatar
                            ? "Avatar ready"
                            : "Headshot ready"}
                    </span>
                  </span>
                </button>
                <input
                  value={item.note}
                  onChange={(e) => patch(item.id, { note: e.target.value })}
                  placeholder="Keep the glasses, warmer coat…"
                  className="mt-2 h-10 w-full rounded-xl border border-line bg-paper px-3 text-sm outline-none"
                />
                <label className="mt-2 flex h-11 cursor-pointer items-center justify-center rounded-full border border-line px-3 text-sm font-medium text-ink">
                  {item.audioBusy ? "Reading audio…" : item.audioName ? item.audioName : "Add their audio"}
                  <input
                    type="file"
                    accept="audio/*"
                    className="sr-only"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      event.target.value = "";
                      void attachAudio(item.id, file);
                    }}
                  />
                </label>
                {item.durationMs ? (
                  <p className="mt-1 text-sm text-muted">Mouth follows this clip · {clock(item.durationMs)}</p>
                ) : null}
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    disabled={!!item.busy}
                    onClick={() => void develop(item.id)}
                    className="h-11 flex-1 rounded-full bg-sienna text-sm font-medium text-cream disabled:opacity-40"
                  >
                    Draw avatar
                  </button>
                  <button
                    type="button"
                    disabled={!item.avatar || !!item.busy}
                    onClick={() => void cutMouths(item.id)}
                    className="h-11 flex-1 rounded-full border border-line text-sm font-medium disabled:opacity-40"
                  >
                    Cut mouths
                  </button>
                </div>
                {item.avatar && (
                  <div className="mt-2 flex items-center gap-4">
                    <button
                      type="button"
                      onClick={() => void keep(item.id)}
                      className="h-11 text-sm font-medium text-sienna"
                    >
                      {item.kept ? "Update saved copy" : "Keep mouth on this face"}
                    </button>
                    <a
                      href={item.avatar}
                      download={`${item.name || "avatar"}.jpg`}
                      className="inline-flex h-11 items-center text-sm text-muted"
                    >
                      Download
                    </a>
                  </div>
                )}
                {item.error && <p className="mt-2 text-sm text-sienna">{item.error}</p>}
              </article>
            ))}
            <p className="px-1 text-sm text-pretty text-muted">
              Mouth buttons use a shared ink kit until you cut a set from that avatar. Add each person’s audio and their mouth follows that voice. The loudest person stays on stage.
            </p>
          </aside>
        </div>
      )}
      </div>

      <section id="mouths" className="jump-target mb-8">
        <h2 className="font-display text-2xl text-ink">Mouth parts</h2>
        <p className="mt-1 max-w-xl text-sm text-muted">
          Drawn for these faces. Each shape is its own picture with a transparent background. Download the six for a person, then set them as that person’s mouth.
        </p>
        <div className="mt-4 flex flex-col gap-6">
          {MOUTH_PEOPLE.map((person) => (
            <div key={person.id}>
              <h3 className="font-display text-xl text-ink">{person.label}</h3>
              <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {MOUTH_SHAPES.map((shape) => (
                  <article key={shape} className="overflow-hidden rounded-2xl border border-line bg-cream">
                    <img loading="lazy"
                      src={`/cast/mouth-parts/${person.id}/${shape}.png?v=3`}
                      alt={`${person.label} ${shape} mouth`}
                      className="aspect-[4/3] w-full cutout object-contain"
                    />
                    <a
                      href={`/cast/mouth-parts/${person.id}/${shape}.png?v=3`}
                      download={`${person.id}-${shape}.png`}
                      target="_blank"
                      rel="noopener"
                      className="flex h-11 items-center justify-center text-sm font-medium text-sienna"
                    >
                      {shape}
                    </a>
                  </article>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section id="backgrounds" className="jump-target mb-8">
        <h2 className="font-display text-2xl text-ink">Backgrounds</h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          {[
            { href: "/backgrounds/coffee-shop.jpg?v=2", file: "coffee-shop.jpg", label: "Coffee shop" },
            { href: "/backgrounds/library.jpg?v=2", file: "library.jpg", label: "Library" },
          ].map((item) => (
            <article key={item.href} className="overflow-hidden rounded-3xl border border-line bg-cream">
              <img loading="lazy" src={item.href} alt={item.label} className="aspect-video w-full object-cover" />
              <div className="flex items-center justify-between gap-3 p-3">
                <span className="text-sm font-medium text-ink">{item.label}</span>
                <a href={item.href} download={item.file} target="_blank" rel="noopener" className="inline-flex h-11 items-center rounded-full bg-sienna px-4 text-sm font-medium text-cream">
                  Download
                </a>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="table" className="jump-target mb-8">
        <h2 className="font-display text-2xl text-ink">At the table</h2>
        <p className="mt-1 text-sm text-muted">Adam is with them. Each person and the table is its own layer.</p>
        <article className="mt-3 overflow-hidden rounded-3xl border border-line bg-cream">
          <img loading="lazy"
            src="/cast/cast-at-the-table.png?v=6"
            alt="Adam, Ben, Corey, Emily, Abby R, and Abby S sitting behind one table"
            className="aspect-video w-full cutout object-contain"
          />
          <div className="flex items-center justify-between gap-3 p-3">
            <span className="text-sm font-medium text-ink">All six, stacked</span>
            <a
              href="/cast/cast-at-the-table.png?v=6"
              download="cast-at-the-table.png"
              target="_blank"
              rel="noopener"
              className="inline-flex h-11 items-center rounded-full bg-sienna px-4 text-sm font-medium text-cream"
            >
              Download
            </a>
          </div>
        </article>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {TABLE_LAYERS.map((layer) => (
            <article key={layer.href} className="overflow-hidden rounded-2xl border border-line bg-cream">
              <img loading="lazy" src={layer.href} alt={layer.label} className="aspect-square w-full cutout object-contain" />
              <a
                href={layer.href}
                download={layer.file}
                target="_blank"
                rel="noopener"
                className="flex h-11 items-center justify-center text-sm font-medium text-sienna"
              >
                {layer.label}
              </a>
            </article>
          ))}
        </div>
      </section>

      <section id="lineup" className="jump-target mb-8">
        <h2 className="font-display text-2xl text-ink">Lined up</h2>
        <p className="mt-1 text-sm text-muted">Each person from the group shot, same size, ready to sit behind the table.</p>
        <article className="mt-3 overflow-hidden rounded-3xl border border-line bg-cream">
          <img loading="lazy" src="/cast/lineup/lined-up.png" alt="The cast lined up behind one table" className="aspect-video w-full cutout object-contain" />
          <div className="flex items-center justify-between gap-3 p-3">
            <span className="text-sm font-medium text-ink">All six in a line</span>
            <a href="/cast/lineup/lined-up.png" download="lined-up.png" target="_blank" rel="noopener" className="inline-flex h-11 items-center rounded-full bg-sienna px-4 text-sm font-medium text-cream">
              Download
            </a>
          </div>
        </article>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {LINEUP.map((item) => (
            <article key={item.href} className="overflow-hidden rounded-2xl border border-line bg-cream">
              <img loading="lazy" src={item.href} alt={item.label} className="aspect-[3/4] w-full cutout object-contain" />
              <a href={item.href} download={item.file} target="_blank" rel="noopener" className="flex h-11 items-center justify-center text-sm font-medium text-sienna">
                {item.label}
              </a>
            </article>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {LINEUP_MOUTHS.map((item) => (
            <article key={item.href} className="overflow-hidden rounded-2xl border border-line bg-cream">
              <img loading="lazy" src={item.href} alt={item.label} className="aspect-[3/2] w-full cutout object-contain" />
              <a href={item.href} download={item.file} target="_blank" rel="noopener" className="flex h-11 items-center justify-center text-sm font-medium text-sienna">
                {item.label}
              </a>
            </article>
          ))}
        </div>
      </section>

      <section id="portraits" className="jump-target mb-8 flex flex-col gap-8">
        {CAST.map((person) => (
          <div key={person.name}>
            <h2 className="font-display text-2xl text-ink">{person.name}</h2>
            <div className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {person.sheets.map((sheet) => (
                <article key={sheet.href} className="overflow-hidden rounded-3xl border border-line bg-cream">
                  <img loading="lazy"
                    src={sheet.href}
                    alt={`${person.name} ${sheet.label}`}
                    className="aspect-[3/4] w-full cutout object-contain"
                  />
                  <div className="flex items-center justify-between gap-3 p-3">
                    <span className="text-sm font-medium text-ink">{sheet.label}</span>
                    <a
                      href={sheet.href}
                      download={sheet.file}
                      target="_blank"
                      rel="noopener"
                      className="inline-flex h-11 items-center rounded-full bg-sienna px-4 text-sm font-medium text-cream"
                    >
                      Download
                    </a>
                  </div>
                </article>
              ))}
            </div>
          </div>
        ))}
      </section>

      {(library.length > 0 || libraryError) && (
        <section className="mt-8">
          <h2 className="font-display text-2xl text-ink">Saved cast</h2>
          {libraryError && <p className="mt-2 text-sm text-sienna">{libraryError}</p>}
          <div className="mt-3 flex gap-3 overflow-x-auto pb-2">
            {library.map((item) => (
              <article key={item.id} className="w-36 shrink-0 rounded-2xl border border-line bg-cream p-2">
                <button type="button" className="w-full text-left" onClick={() => reuse(item)}>
                  <img loading="lazy" src={item.avatar} alt="" className="aspect-portrait w-full rounded-xl object-cover" />
                  <span className="mt-2 block truncate text-sm font-medium text-ink">{item.name}</span>
                </button>
                <button
                  type="button"
                  className="mt-1 h-11 text-sm text-muted"
                  onClick={() => void forget(item.id)}
                >
                  Remove
                </button>
              </article>
            ))}
          </div>
        </section>
      )}
      {seats.map((item) =>
        item.audioUrl ? (
          <audio
            key={item.audioUrl}
            src={item.audioUrl}
            preload="auto"
            ref={(el) => {
              audioRefs.current[item.id] = el;
            }}
          />
        ) : null,
      )}
      <div className="mt-6 border-t border-line bg-paper py-3">
        <div className="mx-auto flex max-w-6xl flex-col gap-3">
          {clipUrl && (
            <video src={clipUrl} controls playsInline className="max-h-40 w-full rounded-xl bg-ink" />
          )}
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="h-11 rounded-full bg-ink px-4 text-sm text-cream disabled:opacity-40"
              disabled={exporting}
              onClick={togglePlay}
            >
              {playing ? "Pause" : "Play"}
            </button>
            <span className="w-16 text-sm tabular-nums text-muted">{clock(playMs)}</span>
            <input
              aria-label="Playback position"
              type="range"
              min={0}
              max={duration}
              step={HOP_MS}
              value={Math.min(playMs, duration)}
              onChange={(event) => {
                setPlaying(false);
                seek(Number(event.target.value));
              }}
              className="h-11 min-w-40 flex-1"
            />
            <span className="w-16 text-sm tabular-nums text-muted">{clock(duration)}</span>
            <button
              type="button"
              className="h-11 rounded-full bg-sienna px-4 text-sm font-medium text-cream disabled:opacity-40"
              disabled={exporting}
              onClick={() => void exportVideo()}
            >
              {exporting ? "Exporting…" : "Export video"}
            </button>
          </div>
          <p className="text-sm text-muted">
            {exportNote ??
              (usingAudio
                ? "Mouths follow the uploaded audio. The bar covers the whole clip, and the loudest voice is on stage."
                : "Add an audio file on each person. Until then, Play runs a short sample.")}
          </p>
        </div>
      </div>
    </main>
      </aside>
    </div>
  );
}
